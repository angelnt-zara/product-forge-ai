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
    --desde-ultima-actividad
                          incluye también hilos con raíz anterior a la fecha
                          pero con respuestas dentro del rango
    --workers N           hilos en paralelo (por defecto 16; ver nota de 429)
    --json                salida JSON en lugar de resumen legible
    --verbose             trazas de progreso a stderr

Nota sobre paralelismo: medido sobre 60 hilos antiguos, 8 workers tardan 4,6 s,
16 tardan 2,3 s y 24 tardan 1,8 s. Se usa 16 como equilibrio: por encima
aparecen 429 de Graph. Los 429 se reintentan con espera exponencial, pero
subir de 24 no acelera y sí aumenta el riesgo de bloqueo temporal.

Salida: JSON con una entrada por hilo relevante (id, webUrl, fecha, título,
autor, nº de respuestas y el texto de cada una).
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

WORKERS_DEFECTO = int(os.environ.get("PF_TEAMS_WORKERS", "16"))


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


# ── Núcleo ───────────────────────────────────────────────────────────────────
def extraer(
    team: str,
    canal: str,
    desde: str,
    *,
    filtro=None,
    desde_ultima_actividad: bool = False,
    workers: int = WORKERS_DEFECTO,
    verbose: bool = False,
) -> list[dict]:
    client = graph_client()

    todos = raices(client, team, canal)
    # Fuera eventos de sistema (altas/bajas de miembros, reuniones).
    todos = [r for r in todos if r.message_type == "message"]
    if verbose:
        print(f"raíces leídas: {len(todos)}", file=sys.stderr)

    en_rango = [r for r in todos if (r.created or "") >= desde]

    # Hilos antiguos que siguen vivos. `lastModifiedDateTime` del raíz NO refleja
    # las respuestas y `replyCount` no viene en Graph beta, así que el único
    # indicio barato es `hasReplies`; luego hay que leer sus respuestas.
    candidatos_antiguos = []
    if desde_ultima_actividad:
        candidatos_antiguos = [
            r for r in todos
            if (r.created or "") < desde and r.raw.get("hasReplies")
        ]
        if verbose:
            print(f"hilos antiguos con hasReplies a revisar: {len(candidatos_antiguos)}", file=sys.stderr)

    objetivos = en_rango + candidatos_antiguos

    with ThreadPoolExecutor(max_workers=workers) as pool:
        reps = list(pool.map(lambda r: respuestas(client, team, canal, r.id), objetivos))

    filas = []
    for raiz, rr in zip(objetivos, reps):
        reciente = any((m.created or "") >= desde for m in rr)
        if (raiz.created or "") < desde and not reciente:
            continue  # antiguo sin actividad en el rango

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
                "respuestas": [
                    {"autor": autor(m), "fecha": a_madrid(m.created), "texto": texto(m)}
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
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args()

    filtro = None
    if a.solo_storefront:
        filtro = lambda t: bool(MENCIÓN_SF.search(t) and URL_PRODUCTO.search(t))  # noqa: E731
    elif a.regex:
        rx = re.compile(a.regex, re.I)
        filtro = lambda t: bool(rx.search(t))  # noqa: E731

    filas = extraer(
        a.team,
        a.canal,
        a.desde,
        filtro=filtro,
        desde_ultima_actividad=a.desde_ultima_actividad,
        workers=a.workers,
        verbose=a.verbose,
    )

    if a.json:
        print(json.dumps(filas, ensure_ascii=False, indent=2))
    else:
        print(f"{len(filas)} hilos relevantes")
        for f in filas:
            marca = " [raíz fuera de rango]" if f["fecha_raiz_fuera_de_rango"] else ""
            print(f"  {f['fecha']} · {f['n_respuestas']:>3} resp · {f['titulo'][:70]}{marca}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
