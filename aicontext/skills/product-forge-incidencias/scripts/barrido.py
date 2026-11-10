#!/usr/bin/env python3
"""Barrido de los 15 canales de incidencias en UNA sola invocación.

Motivo: lanzar 15 subagentes (LLM) para que cada uno ejecute el mismo script
multiplica el coste real, porque cada subagente añade sus propias vueltas de
modelo y acaba reejecutando el script 2-4 veces y verificando por CLI. Aquí el
trabajo de red se hace en un solo proceso, con los canales en paralelo, y deja
un JSON por canal que el agente principal lee y clasifica.

Medido en este workspace: 15 canales en ~75 s (antes, con 15 subagentes, el
informe tardaba ~25 min).

Uso:
    python3 barrido.py <desde_iso> <salida_dir> [opciones]

Opciones:
    --canales 1,2,4       solo esos canales (por defecto, los 15)
    --workers-canal N     canales en paralelo (por defecto 5)
    --workers-hilo N      hilos en paralelo dentro de un canal (por defecto 8)
    --sin-ultima-actividad  no busca hilos antiguos con actividad en el rango
    --sin-resumen         no genera indice.txt (solo los JSON por canal)
    --chars N             truncado del ultimo mensaje en el indice (300)

Ademas de canal_NN.json, deja en el directorio de salida:
    indice.txt            UNA linea por hilo de los 15 canales (~13 KB). Es lo
                          que debe leer el agente para clasificar.
    detalle.py            helper para sacar el texto integro de los hilos
                          candidatos SIN volver a llamar a Teams.

Flujo de lectura recomendado (una sola pasada):
    1. leer indice.txt y decidir que hilos son candidatos;
    2. python3 detalle.py <salida_dir> <id> [<id> ...]  -> texto integro.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

AQUI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("ec", AQUI / "extract_channel.py")
ec = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ec)

# (n, nombre, team_id, channel_id, filtro_reforzado)
CANALES = [
    (1, "SQUAD Product Forge", "1301738f-827e-48ec-8770-3f0922c1c295", "19:c2d93e0c05834c5f885f7ebbb2a82da8@thread.tacv2", False),
    (2, "Incidencias", "1301738f-827e-48ec-8770-3f0922c1c295", "19:d311bbd5ba844456a3f88ca0f8fcc1ec@thread.tacv2", False),
    (3, "PACMAN Contributors", "1301738f-827e-48ec-8770-3f0922c1c295", "19:TFiV3Qv4kALmUMHeZJxzjdivoSYvaQ64PtQ0hPlG0tM1@thread.tacv2", False),
    (4, "B - Gestion incidencias Tecnologia", "fc58da2f-67b0-49ab-a3df-d2b84d676f26", "19:38382f0598414c04b7a4354ea823f795@thread.tacv2", False),
    (5, "P - Dudas tecnicas", "fc58da2f-67b0-49ab-a3df-d2b84d676f26", "19:d63e20f255304e7ea5c97cd0a6ba760c@thread.tacv2", False),
    (6, "PRO Validacion Pruebas", "2f537452-376a-4f33-9599-064664d6bdd9", "19:c3089f466c1d4bdc92182b223200430a@thread.skype", False),
    (7, "Incidencias Entornos Previos", "f74cb4b3-da66-493b-9d82-73c24b3cdfc7", "19:d89dd36e316e46579af64fabe29a63a4@thread.tacv2", False),
    (8, "Q - Soporte API Storefront", "fc58da2f-67b0-49ab-a3df-d2b84d676f26", "19:da2d4f13877c45639e78b833a4140a45@thread.tacv2", True),
    (9, "Imp. Bershka", "1301738f-827e-48ec-8770-3f0922c1c295", "19:4OYdxDq5c2-ke6zi6Yv-GbI6lTOCls0NHQeDZuWmddg1@thread.tacv2", True),
    (10, "Imp. Lefties", "1301738f-827e-48ec-8770-3f0922c1c295", "19:gxYlnS2grspTncMANce2vqY_c9ixe_nHqlLwrRyRGrk1@thread.tacv2", True),
    (11, "Imp. Massimo Dutti", "1301738f-827e-48ec-8770-3f0922c1c295", "19:XH0mKWw2z0beuHP819Yt6YCY9myrNTu3Jr-ZBUlfIqQ1@thread.tacv2", True),
    (12, "Imp. Oysho", "1301738f-827e-48ec-8770-3f0922c1c295", "19:uQnRglYGNy-yYOzMaEFgy5EP9jO8I9z7Z4QSHNKLBTE1@thread.tacv2", True),
    (13, "Imp. Pull and Bear", "1301738f-827e-48ec-8770-3f0922c1c295", "19:tCR1SuX9xZZEImROkyJ5n4AxUX1fSprq3-55DLtazQI1@thread.tacv2", True),
    (14, "Imp. Stradivarius", "1301738f-827e-48ec-8770-3f0922c1c295", "19:mF1UCTeEURR_4mSSlGqMq58IJ_XOaLJqLkEem7e6Mas1@thread.tacv2", True),
    (15, "Imp. Zara Home", "1301738f-827e-48ec-8770-3f0922c1c295", "19:7_n40ZpehZYr-aOqZZ8W1PTa10wZ-o5JCjk6QFpFEr81@thread.tacv2", True),
]

# Canales en los que se exige mención al squad. Los externos de incidencias
# (4-7): es donde hay volumen de otros equipos y hace falta discriminar. El canal
# 3 (PACMAN Contributors) no lo lleva porque el propio canal ya implica al squad.
# El canal 2 (Incidencias 🐞) lleva la relevancia ESTRICTA: además de mención,
# vale la participación de un miembro, pero no basta con que el canal lo implique
# (por ahí entraban asuntos de Tágticos y Grids, como «Información de new in»).
CANALES_CON_MENCION = {4, 5, 6, 7}
CANALES_CON_MENCION_ESTRICTA = {2}


def un_canal(c, desde, dua, workers):
    n, nombre, team, ch, reforzado = c
    filtro = (
        (lambda t: bool(ec.MENCIÓN_SF.search(t) and ec.URL_PRODUCTO.search(t)))
        if reforzado
        else None
    )
    mencion = (
        ec.MENCION_ESTRICTA
        if n in CANALES_CON_MENCION_ESTRICTA
        else (ec.MENCIONES_SQUAD if n in CANALES_CON_MENCION else None)
    )
    t0 = time.monotonic()
    try:
        excluidos: list = []
        filas = ec.extraer(
            team,
            ch,
            desde,
            filtro=filtro,
            mencion_obligatoria=mencion,
            destinatario_externo=reforzado,
            desde_ultima_actividad=dua,
            workers=workers,
            excluidos_out=excluidos,
        )
        return {
            "canal": n,
            "nombre": nombre,
            "filtro": (
                "reforzado Storefront+URL"
                if reforzado
                else (
                    "mención estricta (squad o participación)"
                    if n in CANALES_CON_MENCION_ESTRICTA
                    else ("mención al squad" if mencion else "sin filtro")
                )
            ),
            "hilos": filas,
            # Hilos descartados por relevancia. No se tiran en silencio: el
            # informe los cuenta en «Omitidos» y revisa si alguno es nuestro.
            "excluidos": excluidos,
            "segundos": round(time.monotonic() - t0, 1),
            "error": None,
        }
    except Exception as exc:
        return {
            "canal": n,
            "nombre": nombre,
            "hilos": [],
            "excluidos": [],
            "segundos": round(time.monotonic() - t0, 1),
            "error": str(exc)[:300],
        }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("desde", help="ISO 8601 UTC, p. ej. 2026-10-17T22:00:00Z")
    p.add_argument("salida", help="directorio donde dejar un JSON por canal")
    p.add_argument("--canales", default="")
    p.add_argument("--workers-hilo", type=int, default=8)
    p.add_argument("--workers-canal", type=int, default=15)
    p.add_argument(
        "--desde-ultima-actividad",
        action="store_true",
        help="alias de --sin-ultima-actividad invertido; se acepta por compatibilidad "
        "con la documentación de la skill (la búsqueda de hilos antiguos con "
        "actividad está activa por defecto)",
    )
    p.add_argument("--sin-ultima-actividad", action="store_true")
    p.add_argument("--sin-resumen", action="store_true")
    p.add_argument("--chars", type=int, default=300)
    a = p.parse_args()

    seleccion = CANALES
    if a.canales:
        pedidos = {int(x) for x in a.canales.split(",") if x.strip()}
        seleccion = [c for c in CANALES if c[0] in pedidos]

    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=a.workers_canal) as pool:
        resultados = list(
            pool.map(
                lambda c: un_canal(
                    c,
                    a.desde,
                    not a.sin_ultima_actividad or a.desde_ultima_actividad,
                    a.workers_hilo,
                ),
                seleccion,
            )
        )
    total = time.monotonic() - t0

    for r in resultados:
        (salida / f"canal_{r['canal']:02d}.json").write_text(
            json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        estado = f"ERROR {r['error']}" if r["error"] else f"{len(r['hilos'])} hilos"
        print(f"  canal {r['canal']:>2} {r['nombre'][:34]:<34} {r['segundos']:>6.1f}s  {estado}")

    errores = sum(1 for r in resultados if r["error"])
    print(f"\nTOTAL pared: {total:.1f}s  ({len(seleccion)} canales, {errores} con error)")

    # Índice compacto: una línea por hilo de todos los canales. Es lo que lee el
    # agente; evita que tenga que abrir los ~430 KB de JSON por canal.
    if not a.sin_resumen:
        lineas = [
            f"# ÍNDICE GLOBAL · desde {a.desde} · {len(seleccion)} canales",
            "# «!» = raíz anterior al rango incluida por actividad · «S» = último mensaje del squad",
        ]
        for r in resultados:
            if not r["hilos"]:
                continue
            lineas.append("")
            lineas.append(f"## canal {r['canal']:02d} · {r['nombre']} · {len(r['hilos'])} hilos")
            lineas += [ec.linea_indice(h, a.chars) for h in r["hilos"]]
        texto = "\n".join(lineas) + "\n"
        (salida / "indice.txt").write_text(texto, encoding="utf-8")
        print(f"Índice compacto: {salida / 'indice.txt'}  ({len(texto)/1024:.1f} KB)")

    print(f"JSON por canal en: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
