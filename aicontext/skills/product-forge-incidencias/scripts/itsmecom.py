#!/usr/bin/env python3
"""ITSMECOM citados en cada hilo del barrido, y la JQL para verificarlos.

Motivo: un hilo de Teams puede quedar sin feedback aunque el caso se resuelva en
su Jira, así que el hilo parece pendiente cuando ya no lo es (y al revés: un
ticket puede haberse reasignado fuera de Pacman). Para decidirlo hay que cruzar
los ITSMECOM que cita cada hilo contra Jira por **estado** y **equipo asignado**,
nunca por etiquetas.

Este script hace la parte mecánica y medible de ese cruce:

1. Extrae los ITSMECOM del título y de todas las respuestas de cada hilo de los
   JSON que ya dejó `barrido.py` (no llama a Teams).
2. Emite una única JQL `key in (...)` lista para pegar en `jira_search`, en vez
   de que el agente se monte el extractor a mano en cada informe.

La consulta a Jira y la decisión final (omitir o mantener el hilo) son del
agente: el MCP devuelve el estado y el equipo, y los criterios están en
`clasificacion.md`. Aquí no se consulta Jira porque el token del MCP no está
disponible para los scripts del workspace.

Uso:
    python3 itsmecom.py <dir_salida>
    python3 itsmecom.py <dir_salida> --json
    python3 itsmecom.py <dir_salida> --solo-clave      # solo la JQL

Salida por defecto: una línea por hilo que cita algún ITSMECOM, con canal,
fecha, nº de claves, si el hilo lo abrió un bot y el título. Al final, la JQL.

Con --json: {id_hilo: {canal, canal_nombre, fecha, titulo, autor, bot, claves}}.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Clave de ticket ITSMECOM. Se acepta cualquier separador alrededor porque los
# hilos las escriben como «ITSMECOM-5850604», «[ITSMECOM-5850604]» o dentro de
# una URL de Jira.
CLAVE_RE = re.compile(r"ITSMECOM-(\d+)", re.IGNORECASE)

# Un hilo que cita muchas claves casi siempre es un resumen automático (el bot de
# reuniones volcando el listado de la daily), no un caso concreto. Se marca para
# que el agente no lo confunda con un hilo de incidencia.
UMBRAL_BOT = 5


def claves_del_hilo(hilo: dict) -> list[str]:
    """ITSMECOM citados en el título y en todas las respuestas, sin duplicados.

    El orden es el de aparición (primero el título, luego las respuestas) y las
    claves se normalizan a mayúsculas para que `key in (...)` no dependa de cómo
    las escribiera el autor.
    """
    vistos: dict[str, None] = {}

    def mira(texto: str) -> None:
        for numero in CLAVE_RE.findall(texto or ""):
            vistos.setdefault(f"ITSMECOM-{numero}", None)

    mira(hilo.get("titulo") or "")
    for respuesta in hilo.get("respuestas") or []:
        mira(respuesta.get("texto") or "")
    return list(vistos)


def cargar(dir_salida: Path) -> list[dict]:
    """Hilos del barrido que citan al menos un ITSMECOM."""
    filas: list[dict] = []
    for fichero in sorted(dir_salida.glob("canal_*.json")):
        try:
            datos = json.loads(fichero.read_text(encoding="utf-8"))
        except Exception as exc:  # JSON a medias por un barrido interrumpido
            print(f"aviso: {fichero.name} ilegible ({exc})", file=sys.stderr)
            continue
        for hilo in datos.get("hilos") or []:
            claves = claves_del_hilo(hilo)
            if not claves:
                continue
            autor = hilo.get("autor") or ""
            filas.append(
                {
                    "id": hilo.get("id"),
                    "canal": datos.get("canal"),
                    "canal_nombre": datos.get("nombre"),
                    "fecha": hilo.get("fecha"),
                    "titulo": hilo.get("titulo"),
                    "autor": autor,
                    "bot": autor.startswith("("),
                    "claves": claves,
                }
            )
    filas.sort(key=lambda f: (f["canal"] or 0, f["fecha"] or ""))
    return filas


def jql(filas: list[dict], tamano_lote: int = 40) -> list[str]:
    """JQL `key in (...)` para verificar las claves citadas, troceada.

    Sin trocear, una lista larga (el bot de la daily cita 16 tickets de golpe)
    arriesga URLs demasiado largas. Con 40 por consulta sobra margen y siguen
    siendo una o dos llamadas.
    """
    todas: dict[str, None] = {}
    for fila in filas:
        for clave in fila["claves"]:
            todas.setdefault(clave, None)
    claves = list(todas)
    if not claves:
        return []
    return [
        "key in (" + ",".join(claves[i : i + tamano_lote]) + ")"
        for i in range(0, len(claves), tamano_lote)
    ]


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("salida", help="directorio que dejó barrido.py")
    p.add_argument("--json", action="store_true", help="salida JSON")
    p.add_argument(
        "--solo-clave",
        action="store_true",
        help="imprime solo la JQL de verificación",
    )
    a = p.parse_args()

    salida = Path(a.salida)
    if not salida.is_dir():
        sys.exit(f"no existe el directorio: {salida}")

    filas = cargar(salida)
    consultas = jql(filas)

    if a.solo_clave:
        for consulta in consultas:
            print(consulta)
        return 0

    if a.json:
        print(
            json.dumps(
                {
                    f["id"]: {
                        "canal": f["canal"],
                        "canal_nombre": f["canal_nombre"],
                        "fecha": f["fecha"],
                        "titulo": f["titulo"],
                        "autor": f["autor"],
                        "bot": f["bot"],
                        "claves": f["claves"],
                    }
                    for f in filas
                },
                ensure_ascii=False,
                indent=1,
            )
        )
        return 0

    if not filas:
        print("Ningún hilo del barrido cita un ITSMECOM.")
        return 0

    for f in filas:
        marca = " BOT" if f["bot"] else ""
        aviso = (
            f" · {len(f['claves'])} claves, parece un resumen automático"
            if len(f["claves"]) > UMBRAL_BOT
            else ""
        )
        print(
            f"{f['id']} | c{f['canal']:02d} {f['canal_nombre']} | {f['fecha']} | "
            f"{','.join(f['claves'])}{marca}{aviso} | {(f['titulo'] or '')[:70]}"
        )

    print()
    print("# Verifica en Jira por ESTADO y EQUIPO ASIGNADO (nunca por etiquetas):")
    print("#   project = ITSMECOM AND statusCategory != Done")
    print("#     AND \"Equipo Asignado\" in (jsdsoportepacman)")
    for consulta in consultas:
        print(consulta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
