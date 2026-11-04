#!/usr/bin/env python3
"""Extrae un canal de Teams: raíces en rango + respuestas COMPLETAS paginadas.

No modifica `_shared/scripts`: reutiliza su cliente ya autenticado. El CLI
`teams channel replies` corta en 50 respuestas y no sigue `@odata.nextLink`;
aquí sí se pagina, que es lo que evita que el agente se escriba su propio
extractor en cada ejecución.

Uso:
    python3 extract_channel.py <team_id> <channel_id> <desde_iso> [opciones]

Opciones:
    --sin-filtro          no aplica filtro de relevancia (solo hechos)
    --solo-storefront     filtro reforzado: menciona Storefront Y URL de Producto
    --regex <patron>      filtro propio sobre el texto del hilo completo
    --menciona <a,b>      exige mención al squad (mentions[] o texto) o a una de
                          las palabras separadas por comas
    --desde-ultima-actividad
                          incluye también hilos con raíz anterior a la fecha
                          pero con respuestas dentro del rango
    --workers N           hilos en paralelo (por defecto 8; ver nota de 429)
    --json                salida JSON en lugar de resumen legible
    --resumen             salida de ÍNDICE compacto (una línea por hilo) en lugar
                          del volcado íntegro; es lo que debe leer el agente
    --resumen-chars N     truncado del último mensaje en el índice (por defecto 300)
    --verbose             trazas de progreso a stderr

Nota sobre paralelismo: medido sobre 60 hilos antiguos, 8 workers tardan 4,6 s,
16 tardan 2,3 s y 24 tardan 1,8 s. Se usa 8 por defecto porque varias instancias
del script suelen ejecutarse a la vez (una por canal) y con 8 ya aparecen 429 de
Graph en ejecuciones concurrentes. Los 429 se reintentan con espera exponencial.

Nota sobre hilos antiguos con actividad: se resuelven con `$expand=replies` en la
propia página de raíces, sin una llamada por hilo, y se corta la paginación de un
hilo en cuanto sus respuestas salen del rango (Graph las da de más reciente a más
antigua). Antes, dos hilos de 2025 con 3.000 y 2.601 respuestas costaban 113
llamadas para no aportar nada al informe.

Salida: JSON con una entrada por hilo relevante (id, webUrl, fecha, título,
autor, nº de respuestas, menciones y el texto de cada una).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Localización del paquete compartido ──────────────────────────────────────
# Se resuelve subiendo por los padres: funciona tanto en el repo fuente
# (aicontext/skills/...) como materializado en el workspace (.opencode/skills/...).
_HERE = Path(__file__).resolve()


def _buscar_shared() -> Path | None:
    """Localiza el paquete compartido de Teams.

    Orden: (1) subiendo desde este fichero, que cubre el caso materializado en
    el workspace; (2) desde el directorio de trabajo, que cubre la ejecución
    directa desde el repo fuente, donde `_shared` no existe.
    """
    candidatos = []
    for base in (_HERE.parents[0], Path.cwd()):
        candidatos += [
            base / ".opencode" / "skills" / "_shared" / "scripts",
            base / "skills" / "_shared" / "scripts",
        ]
        candidatos += [
            p / ".opencode" / "skills" / "_shared" / "scripts" for p in base.parents
        ]
    for c in candidatos:
        if (c / "teams").is_dir():
            return c
    return None


_SHARED = _buscar_shared()
if _SHARED is None:  # pragma: no cover
    sys.exit(
        "No encuentro skills/_shared/scripts/teams. Ejecuta el script desde la raíz "
        "del workspace (donde está .opencode/skills/_shared/scripts)."
    )
sys.path.insert(0, str(_SHARED))

from teams.app import create_app                      # noqa: E402
from teams.config import GRAPH_BETA, GRAPH_RESOURCE, TOKEN_CACHE_GRAPH  # noqa: E402
from teams.models import ChannelMessage               # noqa: E402

# ── Zona horaria: Europe/Madrid real, con CET/CEST automático ────────────────
try:
    from zoneinfo import ZoneInfo
    MADRID = ZoneInfo("Europe/Madrid")
except Exception:  # sin tzdata: degradar a CET y avisar
    MADRID = timezone(timedelta(hours=1))
    print("aviso: zoneinfo no disponible, uso CET fijo (+1)", file=sys.stderr)

HREF_RE = re.compile(r'href="([^"]+)"', re.I)
TAG_RE = re.compile(r"<[^>]+>")

# Filtro reforzado de los canales 8-15
URL_PRODUCTO = re.compile(r"/(?:products?(?:Array)?)(?:/|$|[?#])", re.I)
MENCIÓN_SF = re.compile(r"storefront", re.I)

# Etiquetas y nombres del squad que cuentan como mención (canales 2-7).
# Se aplican sobre `mentions[].mentionText` y sobre el texto del mensaje, que es
# lo que antes cada subagente tenía que sacar por su cuenta con el CLI.
MENCIONES_SQUAD = (
    "productforge",
    "product forge",
    "storefront producto",
    "comercialproducto",
    "comercialproductostore",
    "pacman contributors",
    "pacman products",
)

# Miembros del squad (team.adoc, sección ProductForge, más Elias Ferreiro
# Borreiros). Muchos hilos no etiquetan al squad pero sí nombran a una persona
# del equipo; sin esto se perdían hilos reales (p. ej. «Irlanda OY» y «wishlist
# OY» en PRO Validación Pruebas, que solo mencionan a Jose Manuel Neto Delgado).
MIEMBROS_SQUAD = (
    "adrian rabade",
    "angel negrete",
    "alberto barrio",
    "adrian touza",
    "diego garcia ramallal",
    "beatriz adrian",
    "jose baz",
    "juan manuel magarino",
    "luis gijon",
    "aaron blanco",
    "david gomez alvarez",
    "francisco javier corchado",
    "jose manuel neto",
    "vicente vidal",
    "elias ferreiro",
)

WORKERS_DEFECTO = int(os.environ.get("PF_TEAMS_WORKERS", "8"))


# ── Cliente autenticado ──────────────────────────────────────────────────────
def graph_client():
    """Devuelve un cliente con token de `az` para Graph beta.

    Intenta primero el cliente del paquete compartido; si su estructura interna
    cambia (el atributo es privado), construye uno propio con sus piezas
    públicas en lugar de romperse con AttributeError.
    """
    app = create_app()
    graph = app.graph

    az = getattr(graph, "_az", None)
    if az is not None:
        return az

    print(
        "aviso: no encuentro el cliente interno del paquete compartido; "
        "construyo uno propio con AzTokenProvider",
        file=sys.stderr,
    )
    from teams.auth.az import AzTokenProvider
    from teams.auth.cache import TokenCache
    from teams.http import HttpClient

    return HttpClient(auth=AzTokenProvider(GRAPH_RESOURCE, TokenCache(TOKEN_CACHE_GRAPH)))


# ── Utilidades de texto ──────────────────────────────────────────────────────
def texto(m) -> str:
    """Texto plano del mensaje."""
    if isinstance(m, ChannelMessage):
        return m.text or ""
    cuerpo = (m.get("body") or {}).get("content") or ""
    return html.unescape(re.sub(r"\s+", " ", TAG_RE.sub(" ", cuerpo))).strip()


def enlaces(m) -> list[str]:
    """URLs reales del mensaje.

    Teams trunca el texto VISIBLE de los enlaces con «…»; la URL completa solo
    está en el atributo href. Sin esto, el filtro por URL de Producto produce
    falsos negativos (comprobado con «Dudas Massimo Dutti»).
    """
    raw = m.raw if isinstance(m, ChannelMessage) else (m or {})
    return HREF_RE.findall(((raw.get("body") or {}).get("content") or ""))


def a_madrid(iso: str) -> str:
    if not iso:
        return "-"
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return d.astimezone(MADRID).strftime("%d/%m/%Y %H:%M")


def autor(m) -> str:
    if isinstance(m, ChannelMessage):
        return m.author or "(bot)"
    return ((m.get("from") or {}).get("user") or {}).get("displayName") or "(bot)"


def _sin_tildes(s: str) -> str:
    """Minúsculas y sin tildes, para comparar etiquetas y nombres del squad."""
    tabla = str.maketrans("áéíóúüàèìòùâêîôûñç", "aeiouuaeiouaeiounc")
    return s.lower().translate(tabla)


def menciones(m) -> list[str]:
    """Etiquetas mencionadas en el mensaje (`mentions[].mentionText`).

    `ChannelMessage` no expone `mentions`, así que antes cada subagente tenía que
    sacarlas con el CLI en un volcado aparte. Ahora salen del `raw`.
    """
    raw = m.raw if isinstance(m, ChannelMessage) else (m or {})
    salida = []
    for men in raw.get("mentions") or []:
        texto = men.get("mentionText") or ((men.get("mentioned") or {}).get("user") or {}).get("displayName")
        if texto:
            salida.append(str(texto))
    return salida


def es_del_squad(nombre: str) -> bool:
    """True si el nombre corresponde a un miembro de ProductForge."""
    limpio = _sin_tildes(nombre or "")
    return any(p in limpio for p in MIEMBROS_SQUAD)


def menciona_squad(
    m,
    etiquetas: tuple[str, ...] = MENCIONES_SQUAD,
    miembros: tuple[str, ...] = MIEMBROS_SQUAD,
) -> bool:
    """True si el mensaje menciona al squad.

    Las etiquetas y nombres del squad se buscan en `mentions` **y** en el texto
    (hay quien escribe «ProductForge» sin etiquetar). Los nombres de personas se
    buscan **solo** en `mentions`: así no se confunde una respuesta escrita por un
    miembro del squad con una mención a ese miembro.
    """
    mencionados = [_sin_tildes(x) for x in menciones(m)]
    if any(any(p in men for p in miembros) for men in mencionados):
        return True
    for c in mencionados + [_sin_tildes(texto(m))]:
        if any(p in c for p in etiquetas):
            return True
    return False


# ── GET con reintento ────────────────────────────────────────────────────────
def _get(client, url: str, intentos: int = 3):
    """GET con reintento: Graph devuelve timeouts y 429 esporádicos."""
    for i in range(intentos):
        try:
            return client.get(url)
        except Exception as exc:
            es_429 = "429" in str(exc)
            if i == intentos - 1:
                raise
            espera = (2 ** i) * (2 if es_429 else 1)
            print(f"aviso: reintento {i+1}/{intentos} en {espera}s ({exc})", file=sys.stderr)
            time.sleep(espera)


# ── Lectura paginada ─────────────────────────────────────────────────────────
def respuestas(client, team: str, canal: str, mid: str, tope_paginas: int = 20) -> list:
    """TODAS las respuestas de un hilo, siguiendo @odata.nextLink."""
    url = f"{GRAPH_BETA}/teams/{team}/channels/{canal}/messages/{mid}/replies?$top=50"
    salida, pagina = [], 0
    while url and pagina < tope_paginas:
        try:
            datos = _get(client, url)
        except Exception as exc:  # 404 de mensaje borrado, 429 persistente, etc.
            print(f"aviso: respuestas de {mid} ilegibles ({exc})", file=sys.stderr)
            break
        salida.extend(ChannelMessage.from_json(x) for x in datos.get("value", []))
        pagina += 1
        url = datos.get("@odata.nextLink")
    return salida


def raices(client, team: str, canal: str, paginas: int = 8) -> list:
    """Posts raíz del canal, siguiendo @odata.nextLink."""
    url = f"{GRAPH_BETA}/teams/{team}/channels/{canal}/messages?$top=50"
    salida, pagina = [], 0
    while url and pagina < paginas:
        datos = _get(client, url)
        salida.extend(ChannelMessage.from_json(x) for x in datos.get("value", []))
        pagina += 1
        url = datos.get("@odata.nextLink")
    return salida


# Nota de rendimiento (medido en este workspace):
#  - canal 4 (302 hilos, 4.711 respuestas): 43 s con una llamada por hilo → 16 s
#    con `$expand=replies`.
#  - canal 1 (316 hilos, 7.847 respuestas): 58 s con una llamada por hilo, 146 s
#    con `$expand` completo y 18 s con `$expand` + corte por fecha.
# El corte por fecha de las respuestas es lo que hace que `$expand` gane siempre:
# los dos hilos de 2025 con 3.000 y 2.601 respuestas costaban 113 páginas.


def raices_con_respuestas(
    client, team: str, canal: str, desde: str = "", paginas: int = 8
) -> tuple[list, dict[str, list]]:
    """Posts raíz del canal CON sus respuestas incrustadas en la misma página.

    `$expand=replies` devuelve hasta 200 respuestas por hilo dentro de la propia
    página de raíces, así que un canal completo se resuelve en ~8 llamadas en vez
    de una por hilo. Además encuentra más hilos con respuestas que `hasReplies`
    (345 frente a 302 en el canal 4, sin perder ninguno).

    Los hilos con más de 200 respuestas traen `replies@odata.nextLink`. Se sigue,
    pero **solo mientras las respuestas vistas sigan dentro del rango**: Graph las
    devuelve ordenadas de más reciente a más antigua, así que al aparecer una
    anterior a `desde` el resto ya no interesa. Sin este corte, dos hilos de 2025
    con 3.000 y 2.601 respuestas costaban 113 páginas (275 llamadas y +90 s en el
    canal 1) para no aportar nada al informe.

    Devuelve (raíces, {id_raiz: [respuestas]}).
    """
    url = f"{GRAPH_BETA}/teams/{team}/channels/{canal}/messages?$top=50&$expand=replies"
    raices_, por_hilo = [], {}
    pagina = 0
    while url and pagina < paginas:
        datos = _get(client, url)
        for bruto in datos.get("value", []):
            raiz = ChannelMessage.from_json(bruto)
            raices_.append(raiz)
            rr = [ChannelMessage.from_json(x) for x in (bruto.get("replies") or [])]
            siguiente = bruto.get("replies@odata.nextLink")
            while siguiente and (not desde or all((m.created or "") >= desde for m in rr[-50:])):
                extra = _get(client, siguiente)
                rr.extend(ChannelMessage.from_json(x) for x in extra.get("value", []))
                siguiente = extra.get("@odata.nextLink")
            por_hilo[raiz.id] = rr
        pagina += 1
        url = datos.get("@odata.nextLink")
    return raices_, por_hilo


# ── Núcleo ───────────────────────────────────────────────────────────────────
def extraer(
    team: str,
    canal: str,
    desde: str,
    *,
    filtro=None,
    mencion_obligatoria: tuple[str, ...] | None = None,
    desde_ultima_actividad: bool = False,
    workers: int = WORKERS_DEFECTO,
    verbose: bool = False,
) -> list[dict]:
    client = graph_client()

    todos, por_hilo = [], {}
    try:
        todos, por_hilo = raices_con_respuestas(client, team, canal, desde)
    except Exception as exc:
        # Si `$expand=replies` fallara (cambio de contrato de Graph, 400…), se
        # degrada a la vía clásica: listado plano + respuestas hilo a hilo.
        print(f"aviso: $expand=replies no disponible ({exc}); vía clásica", file=sys.stderr)
        todos = raices(client, team, canal)
    # Fuera eventos de sistema (altas/bajas de miembros, reuniones).
    todos = [r for r in todos if r.message_type == "message"]

    if verbose:
        print(
            f"raíces leídas: {len(todos)}"
            + (" (respuestas incluidas en la misma página)" if por_hilo else ""),
            file=sys.stderr,
        )

    en_rango = [r for r in todos if (r.created or "") >= desde]

    # Hilos antiguos que siguen vivos. `lastModifiedDateTime` del raíz NO refleja
    # las respuestas (verificado: 0 de 323 raíces antiguos lo actualizan) y
    # `replyCount` no viene informado en Graph beta. Si las respuestas vinieron
    # incrustadas no hay llamadas extra: solo se comprueba la fecha.
    candidatos_antiguos = []
    if desde_ultima_actividad:
        for r in todos:
            if (r.created or "") >= desde:
                continue
            if any((m.created or "") >= desde for m in por_hilo.get(r.id, [])):
                candidatos_antiguos.append(r)
        if verbose:
            print(
                f"hilos antiguos con actividad en el rango: {len(candidatos_antiguos)}",
                file=sys.stderr,
            )

    objetivos = en_rango + candidatos_antiguos

    # Solo hace falta pedir respuestas sueltas si no vinieron incrustadas (vía de
    # respaldo). Con `$expand=replies` los hilos sin respuestas vienen con lista
    # vacía, que es un hecho, no un fallo de lectura.
    faltan = [r for r in objetivos if r.id not in por_hilo]
    if faltan:
        if verbose:
            print(f"hilos a completar por separado: {len(faltan)}", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            completas = list(pool.map(lambda r: respuestas(client, team, canal, r.id), faltan))
        for r, rr in zip(faltan, completas):
            por_hilo[r.id] = rr

        if desde_ultima_actividad:
            # Sin `hasReplies` no se pueden descartar antes: se revisan ahora, con
            # las respuestas ya leídas, para no perder hilos antiguos vivos.
            conocidos = {r.id for r in objetivos}
            for r in todos:
                if r.id in conocidos or (r.created or "") >= desde:
                    continue
                if any((m.created or "") >= desde for m in por_hilo.get(r.id, [])):
                    objetivos.append(r)

    filas = []
    for raiz in objetivos:
        rr = por_hilo.get(raiz.id, [])
        # Graph devuelve las respuestas de más reciente a más antigua. Se ordenan
        # aquí para que `ultima_actividad` y el orden de salida sean correctos:
        # antes se usaba `rr[-1]`, que es la MÁS ANTIGUA, y daba una fecha falsa.
        rr = sorted(rr, key=lambda m: m.created or "")
        reciente = any((m.created or "") >= desde for m in rr)
        if (raiz.created or "") < desde and not reciente:
            continue  # antiguo sin actividad en el rango

        if mencion_obligatoria:
            # Relevante si algún mensaje menciona al squad o si el hilo lo abrió un
            # miembro del equipo (sus hilos en Incidencias 🐞 son trabajo del squad
            # aunque no se etiquete a sí mismo).
            if not any(menciona_squad(m) for m in [raiz] + rr) and not es_del_squad(autor(raiz)):
                continue

        cuerpo = " ".join(
            [texto(raiz)]
            + [texto(m) for m in rr]
            + enlaces(raiz)
            + [h for m in rr for h in enlaces(m)]
        )
        if filtro and not filtro(cuerpo):
            continue

        filas.append(
            {
                "id": raiz.id,
                "webUrl": raiz.raw.get("webUrl"),
                "fecha": a_madrid(raiz.created),
                "fecha_raiz_fuera_de_rango": (raiz.created or "") < desde,
                "titulo": raiz.raw.get("subject") or (texto(raiz)[:90] or "(sin asunto)"),
                "autor": autor(raiz),
                "n_respuestas": len(rr),
                "ultima_actividad": a_madrid(rr[-1].created) if rr else a_madrid(raiz.created),
                "menciones_squad": sorted(
                    {
                        men
                        for m in [raiz] + rr
                        for men in menciones(m)
                        if any(p in _sin_tildes(men) for p in MENCIONES_SQUAD)
                    }
                ),
                "respuestas": [
                    {
                        "autor": autor(m),
                        "fecha": a_madrid(m.created),
                        "texto": texto(m),
                        "menciones": menciones(m),
                    }
                    for m in rr
                ],
                "urls_producto": [
                    u for u in (enlaces(raiz) + [h for m in rr for h in enlaces(m)])
                    if URL_PRODUCTO.search(u)
                ],
            }
        )

    filas.sort(key=lambda f: f["fecha"])
    return filas


# ── Índice compacto (lectura en una sola pasada) ─────────────────────────────
# Motivo: el volcado íntegro de los 15 canales son ~430 KB de JSON, de los que
# el 83 % del texto se descarta al clasificar (medido: 130.529 de 157.594
# caracteres). Con el índice el agente lee una línea por hilo (~13 KB), decide
# cuáles son candidatos y pide el texto íntegro solo de esos (~26 KB). Es el
# mismo dato, leído una vez en vez de tres.
def _ultimo(f: dict):
    return f["respuestas"][-1] if f["respuestas"] else None


def linea_indice(f: dict, chars: int = 300) -> str:
    """Una línea por hilo con lo justo para triage: quién, cuándo, cuánto, qué."""
    resp = f["respuestas"]
    squad = [r for r in resp if es_del_squad(r["autor"])]
    ult = _ultimo(f)
    ult_autor = ult["autor"] if ult else f["autor"]
    ult_squad = "S" if (ult and es_del_squad(ult["autor"])) else "-"
    cuerpo = (ult["texto"] if ult else "") or ""
    if len(cuerpo) > chars:
        cuerpo = cuerpo[:chars].rstrip() + "…"
    cuerpo = re.sub(r"\s+", " ", cuerpo)
    fuera = "!" if f["fecha_raiz_fuera_de_rango"] else "-"
    return (
        f"{f['id']} | {f['fecha'][:10]} {fuera} | {f['autor']} | "
        f"resp={f['n_respuestas']:>3} squad={len(squad):>2} | "
        f"ult={f['ultima_actividad'][:10]} {ult_squad} {ult_autor} | "
        f"urls={len(f['urls_producto'])} | {f['titulo'][:90]} | {cuerpo}"
    )


def resumen(filas: list[dict], chars: int = 300) -> str:
    """Índice legible: cabecera con recuentos y una línea por hilo."""
    total = len(filas)
    sin_resp = sum(1 for f in filas if f["n_respuestas"] == 0)
    sin_squad = sum(
        1 for f in filas if not any(es_del_squad(r["autor"]) for r in f["respuestas"])
    )
    cabecera = (
        f"# ÍNDICE · {total} hilos · {sin_resp} sin respuestas · "
        f"{sin_squad} sin respuesta del squad\n"
        f"# id | fecha fueraDeRango | autor | respuestas squad | últimaActividad "
        f"últimoEsDelSquad últimoAutor | urlsProducto | título | último mensaje\n"
        f"# «!» = raíz anterior al rango, incluida por actividad. "
        f"«S» = el último mensaje es del squad."
    )
    return cabecera + "\n" + "\n".join(linea_indice(f, chars) for f in filas)


def detalle(filas: list[dict], ids: list[str]) -> str:
    """Texto íntegro de los hilos indicados, a partir de filas ya extraídas."""
    por_id = {f["id"]: f for f in filas}
    partes = []
    for i in ids:
        f = por_id.get(i)
        if f is None:
            partes.append(f"### {i}\n(no está en este canal)")
            continue
        partes.append(
            f"### {f['id']} · {f['fecha']} · {f['autor']} · "
            f"{f['n_respuestas']} respuestas\n"
            f"TÍTULO: {f['titulo']}\n"
            f"WEBURL: {f['webUrl']}\n"
            f"MENCIONES_SQUAD: {', '.join(f['menciones_squad']) or '-'}\n"
            f"URLS_PRODUCTO: {'; '.join(f['urls_producto']) or '-'}"
        )
        for r in f["respuestas"]:
            marca = "SQUAD" if es_del_squad(r["autor"]) else "     "
            partes.append(f"  [{marca}] {r['fecha']} {r['autor']}: {r['texto']}")
    return "\n".join(partes)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("team")
    p.add_argument("canal")
    p.add_argument("desde", help="ISO 8601 UTC, p. ej. 2026-10-17T22:00:00Z")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--sin-filtro", action="store_true")
    g.add_argument("--solo-storefront", action="store_true")
    g.add_argument("--regex")
    p.add_argument("--desde-ultima-actividad", action="store_true")
    p.add_argument("--workers", type=int, default=WORKERS_DEFECTO)
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--resumen",
        action="store_true",
        help="índice compacto: una línea por hilo (lo que debe leer el agente)",
    )
    p.add_argument(
        "--resumen-chars",
        type=int,
        default=300,
        help="truncado del último mensaje en el índice (por defecto 300)",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--menciona",
        nargs="?",
        const="__defecto__",
        default=None,
        help="exige mención al squad por etiqueta o texto; sin valor usa las etiquetas "
        "y nombres del squad, con valor es una lista separada por comas",
    )
    a = p.parse_args()

    filtro = None
    if a.solo_storefront:
        filtro = lambda t: bool(MENCIÓN_SF.search(t) and URL_PRODUCTO.search(t))  # noqa: E731
    elif a.regex:
        rx = re.compile(a.regex, re.I)
        filtro = lambda t: bool(rx.search(t))  # noqa: E731

    mencion_obligatoria = None
    if a.menciona:
        mencion_obligatoria = (
            MENCIONES_SQUAD
            if a.menciona == "__defecto__"
            else tuple(_sin_tildes(x.strip()) for x in a.menciona.split(",") if x.strip())
        )

    filas = extraer(
        a.team,
        a.canal,
        a.desde,
        filtro=filtro,
        mencion_obligatoria=mencion_obligatoria,
        desde_ultima_actividad=a.desde_ultima_actividad,
        workers=a.workers,
        verbose=a.verbose,
    )

    if a.json:
        print(json.dumps(filas, ensure_ascii=False, indent=2))
    elif a.resumen:
        print(resumen(filas, a.resumen_chars))
    else:
        print(f"{len(filas)} hilos relevantes")
        for f in filas:
            marca = " [raíz fuera de rango]" if f["fecha_raiz_fuera_de_rango"] else ""
            print(
                f"  {f['fecha']} · {f['n_respuestas']:>3} resp · "
                f"últ. {f['ultima_actividad']} · {f['titulo'][:70]}{marca}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
