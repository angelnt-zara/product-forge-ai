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
    python3 detalle.py <dir_salida> --todos-los-pendientes   # no: no hay criterio
    python3 detalle.py <dir_salida> --listar                 # ids del índice

Opciones:
    --canal N          limita la búsqueda a ese canal (más rápido)
    --max-resp N       solo las N respuestas MÁS RECIENTES de cada hilo
    --chars N          trunca cada respuesta a N caracteres (0 = íntegra)

Los ids son los de la primera columna de `indice.txt`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


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
    p.add_argument("salida", help="directorio que dejó barrido.py")
    p.add_argument("ids", nargs="*", help="ids de hilo (1ª columna de indice.txt)")
    p.add_argument("--canal", type=int, default=None)
    p.add_argument("--max-resp", type=int, default=0)
    p.add_argument("--chars", type=int, default=0)
    p.add_argument("--listar", action="store_true", help="lista los ids disponibles")
    a = p.parse_args()

    salida = Path(a.salida)
    if not salida.is_dir():
        sys.exit(f"no existe el directorio: {salida}")

    por_id = cargar(salida, a.canal)

    if a.listar:
        for i, h in sorted(por_id.items(), key=lambda kv: kv[1]["fecha"]):
            print(f"{i} | c{h['_canal']:02d} | {h['fecha']} | {h['titulo'][:80]}")
        return 0

    if not a.ids:
        sys.exit("indica al menos un id (o usa --listar)")

    faltan = [i for i in a.ids if i not in por_id]
    for i in a.ids:
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
        print(f"URLS_PRODUCTO: {'; '.join(h.get('urls_producto') or []) or '-'}")
        resp = h.get("respuestas") or []
        if a.max_resp:
            resp = resp[-a.max_resp :]
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
