#!/usr/bin/env python3
"""Texto íntegro de hilos concretos, SIN volver a llamar a Teams.

Segunda mitad del flujo de lectura en una sola pasada: `barrido.py` ya dejó el
índice y los JSON por canal en disco; aquí solo se relee lo que el agente ha
marcado como candidato tras leer `indice.txt`.

Motivo: en el informe del 18/10-04/11 se leyeron 550 KB (JSON completo + un
digest intermedio + relectura de ~30 hilos) para acabar clasificando 26 KB de
texto útil. Con este helper el agente lee el índice (13 KB), decide, y pide solo
los candidatos.

Uso:
    python3 detalle.py <dir_salida> <id> [<id> ...]
    python3 detalle.py <dir_salida> --canal 4 <id> [<id> ...]
    python3 detalle.py <dir_salida> --listar                 # ids del índice

Una SOLA invocación con todos los candidatos: decidirlos tras leer `indice.txt`
y pasarlos de golpe. Antes se hacía en 4 tandas según se iban descubriendo, y
eso son 3 vueltas de modelo de más.

Opciones:
    --canal N          limita la búsqueda a ese canal (más rápido)
    --max-resp N       solo las N respuestas MÁS RECIENTES de cada hilo
    --chars N          trunca cada respuesta a N caracteres (0 = íntegra)
    --completas        no aplica el recorte automático de hilos largos

Los ids son los de la primera columna de `indice.txt`. Se aceptan separados por
espacios, comas o dentro de un único argumento entrecomillado
(`"1793 1794"`, `1793,1794`): antes, un argumento con varios ids se trataba como
un id único, no se encontraba y el comando salía con 0 bytes de detalle, que es
indistinguible de «no hay nada que leer» y lleva a clasificar a ciegas.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent

# Hilos largos: por encima de este número de respuestas se leen solo las N más
# recientes. Medido en el informe del 18/10-04/11: 5 hilos concentraban 130 KB
# de los 430 KB del JSON, y los 3 que se abrieron completos (67 KB) se
# resolvían igual con las 12 últimas respuestas (8,7 KB, -87 %). El estado de un
# hilo lo decide su cola, no su cabecera.
UMBRAL_LARGO = 20
MAX_RESP_LARGO = 12


def normaliza_ids(brutos: list[str]) -> list[str]:
    """Acepta ids separados por espacios o comas, también dentro de un argumento.

    Sin esto, `detalle.py <dir> "1793 1794"` buscaba un id llamado «1793 1794»,
    no lo encontraba y devolvía 0 bytes: un fallo silencioso que parece «no hay
    detalle». Se conserva el orden de aparición y se quitan duplicados.
    """
    vistos: dict[str, None] = {}
    for bruto in brutos:
        for trozo in re.split(r"[\s,;]+", bruto or ""):
            if trozo:
                vistos.setdefault(trozo, None)
    return list(vistos)


def cargar(dir_salida: Path, canal: int | None = None) -> dict[str, dict]:
    """id -> fila de hilo, leyendo los JSON que dejó el barrido."""
    por_id: dict[str, dict] = {}
    patron = f"canal_{canal:02d}.json" if canal else "canal_*.json"
    for fichero in sorted(dir_salida.glob(patron)):
        try:
            datos = json.loads(fichero.read_text(encoding="utf-8"))
        except Exception as exc:  # JSON a medias por un barrido interrumpido
            print(f"aviso: {fichero.name} ilegible ({exc})", file=sys.stderr)
            continue
        for h in datos.get("hilos") or []:
            h["_canal"] = datos.get("canal")
            h["_canal_nombre"] = datos.get("nombre")
            por_id[h["id"]] = h
    return por_id


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # `parse_intermixed_args` permite que las opciones vayan mezcladas con los ids
    # (`detalle.py <dir> --chars 500 <id>`), que es el orden natural al componer el
    # comando. Con `parse_args`, argparse tomaba `--chars` como un id más y abortaba
    # con "unrecognized arguments"; con `parse_known_args` seguía fallando porque
    # el primer posicional ya cerraba la lista.
    p.add_argument("salida", help="directorio que dejó barrido.py")
    p.add_argument("ids", nargs="*", help="ids de hilo (1ª columna de indice.txt)")
    p.add_argument("--canal", type=int, default=None)
    p.add_argument("--max-resp", type=int, default=0)
    p.add_argument("--chars", type=int, default=0)
    p.add_argument(
        "--completas",
        action="store_true",
        help=f"no recorta automáticamente los hilos de más de {UMBRAL_LARGO} respuestas",
    )
    p.add_argument("--listar", action="store_true", help="lista los ids disponibles")
    a = p.parse_intermixed_args()

    salida = Path(a.salida)
    if not salida.is_dir():
        sys.exit(f"no existe el directorio: {salida}")

    por_id = cargar(salida, a.canal)

    if a.listar:
        for i, h in sorted(por_id.items(), key=lambda kv: kv[1]["fecha"]):
            print(f"{i} | c{h['_canal']:02d} | {h['fecha']} | {h['titulo'][:80]}")
        return 0

    ids = normaliza_ids(a.ids)
    if not ids:
        sys.exit("indica al menos un id (o usa --listar)")

    faltan = [i for i in ids if i not in por_id]
    for i in ids:
        h = por_id.get(i)
        if h is None:
            continue
        print(
            f"\n### {i} · canal {h['_canal']:02d} {h['_canal_nombre']} · "
            f"{h['fecha']} · {h['autor']} · {h['n_respuestas']} respuestas"
        )
        print(f"TÍTULO: {h['titulo']}")
        print(f"WEBURL: {h['webUrl']}")
        print(f"MENCIONES_SQUAD: {', '.join(h.get('menciones_squad') or []) or '-'}")
        print(f"MENCIONES_OTRAS: {', '.join(h.get('menciones_otras') or []) or '-'}")
        print(f"RECLAMA_A_OTRO: {'SÍ' if h.get('reclama_a_otro') else 'no'}")
        print(f"URLS_PRODUCTO: {'; '.join(h.get('urls_producto') or []) or '-'}")
        # El cuerpo del raíz debe mostrarse siempre: en un hilo sin respuestas es
        # el único contenido disponible, y quien lo abrió puede estar pidiendo a
        # OTRO equipo que revise lo suyo, lo que no es trabajo de este squad.
        print(f"RAÍZ: {h.get('texto_raiz') or '(sin texto)'}")
        resp = h.get("respuestas") or []
        # Recorte automático de hilos largos, salvo que se pidan completas o se
        # fije --max-resp a mano.
        tope = a.max_resp
        if not tope and not a.completas and len(resp) > UMBRAL_LARGO:
            tope = MAX_RESP_LARGO
            print(
                f"AVISO: hilo largo ({len(resp)} respuestas), se muestran las "
                f"{MAX_RESP_LARGO} más recientes. Usa --completas o --max-resp N "
                f"para verlo entero."
            )
        if tope:
            resp = resp[-tope:]
        for r in resp:
            t = r.get("texto") or ""
            if a.chars and len(t) > a.chars:
                t = t[: a.chars].rstrip() + "…"
            print(f"  - {r['fecha']} {r['autor']}: {t}")

    if faltan:
        print(
            f"\naviso: {len(faltan)} id(s) no encontrados en {salida}: {', '.join(faltan)}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
