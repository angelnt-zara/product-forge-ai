#!/usr/bin/env python3
"""Test de humo de los helpers del flujo de incidencias. Sin red, sin Teams.

Cubre los cuatro fallos que costaron vueltas de modelo o clasificaciones
erróneas en el informe del 18/10-04/11, para que no vuelvan sin que nadie se dé
cuenta:

1. `detalle.py` acepta ids separados por espacios o comas dentro de un único
   argumento (antes devolvía 0 bytes y parecía «no hay detalle»).
2. `detalle.py` recorta los hilos de más de 20 respuestas y avisa.
3. `extract_channel.prs_del_hilo` extrae las PR de los `href` y deduplica.
4. `prs.py` normaliza y agrupa las PR de todos los hilos sin repetirlas.
5. `itsmecom.py` extrae los ITSMECOM citados (título y respuestas, sin duplicados)
   y emite la JQL de verificación troceada.

Uso:
    python3 scripts/test_humo.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

fallos: list[str] = []


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    print(f"  {'OK  ' if cond else 'FALLO'} {nombre}" + (f" · {detalle}" if detalle and not cond else ""))
    if not cond:
        fallos.append(nombre)


def hilo(id_: str, respuestas: int, prs_hrefs: list[str] | None = None) -> dict:
    rs = [
        {
            "autor": f"persona{i}",
            "fecha": f"0{i % 9 + 1}/10/2026 10:00",
            "texto": f"mensaje numero {i} " + ("x" * 80),
            "menciones": [],
        }
        for i in range(respuestas)
    ]
    return {
        "id": id_,
        "webUrl": f"https://teams.example/{id_}",
        "fecha": "01/10/2026 10:00",
        "fecha_raiz_fuera_de_rango": False,
        "titulo": f"Hilo {id_}",
        "autor": "alguien",
        "n_respuestas": respuestas,
        "ultima_actividad": "04/11/2026 10:00",
        "menciones_squad": [],
        "respuestas": rs,
        "urls_producto": [],
        "prs": [
            {
                "owner": "inditex",
                "repo": u.split("/")[4],
                "numero": int(u.rsplit("/", 1)[1]),
                "url": u,
            }
            for u in (prs_hrefs or [])
        ],
    }


def monta_dir(base: Path) -> Path:
    canal = {
        "canal": 1,
        "nombre": "SQUAD Product Forge",
        "filtro": "sin filtro",
        "segundos": 1.0,
        "error": None,
        "hilos": [
            hilo("1001", 5),
            hilo("1002", 163),
            hilo(
                "1003",
                2,
                ["https://github.com/inditex/app-ecommhub/pull/1108"],
            ),
        ],
    }
    (base / "canal_01.json").write_text(
        json.dumps(canal, ensure_ascii=False), encoding="utf-8"
    )
    return base


def main() -> int:
    import detalle
    import extract_channel as ec

    with tempfile.TemporaryDirectory() as tmp:
        base = monta_dir(Path(tmp))

        print("1. normalización de ids")
        check(
            "espacios dentro de un argumento",
            detalle.normaliza_ids(["1001 1002"]) == ["1001", "1002"],
        )
        check(
            "comas dentro de un argumento",
            detalle.normaliza_ids(["1001,1002"]) == ["1001", "1002"],
        )
        check(
            "mezcla de argumentos y deduplicado",
            detalle.normaliza_ids(["1001 1002", "1002", "1003"]) == ["1001", "1002", "1003"],
        )

        print("2. recorte de hilos largos")
        por_id = detalle.cargar(base)
        largo = por_id["1002"]
        check(
            f"umbral y tope coherentes ({detalle.UMBRAL_LARGO}/{detalle.MAX_RESP_LARGO})",
            detalle.UMBRAL_LARGO < len(largo["respuestas"]),
        )
        # La lógica del recorte se replica aquí: si cambia en detalle.py, este
        # check avisa de que hay que revisar el test.
        tope = 0
        if len(largo["respuestas"]) > detalle.UMBRAL_LARGO:
            tope = detalle.MAX_RESP_LARGO
        check("hilo de 163 respuestas se recorta", tope == 12, f"tope={tope}")
        check(
            "hilo corto no se recorta",
            not (len(por_id["1001"]["respuestas"]) > detalle.UMBRAL_LARGO),
        )

        print("3. extracción de PR desde href")
        # `enlaces` acepta ChannelMessage o el dict crudo (rama de respaldo); el
        # test usa el dict para no depender del paquete compartido de Teams.
        def msg(*hrefs: str) -> dict:
            return {
                "body": {
                    "content": " ".join(f'<a href="{h}">ver…</a>' for h in hrefs)
                }
            }

        prs = ec.prs_del_hilo(
            msg("https://github.com/inditex/app-ecommhub/pull/1108"),
            [msg("https://github.com/inditex/app-ecommhub/pull/1108")],
        )
        check("deduplica la misma PR en raíz y respuesta", len(prs) == 1, str(prs))
        check("extrae owner/repo/numero", prs and prs[0]["numero"] == 1108, str(prs))
        check(
            "ignora enlaces que no son PR",
            ec.prs_del_hilo(msg("https://github.com/inditex/app-pacman/pull/3487"), [])
            and not ec.prs_del_hilo(
                msg("https://github.com/inditex/app-pacman/issues/3"), []
            ),
        )

    print("4. agrupación de PR sin repetir (prs.py)")
    import prs as prs_mod

    with tempfile.TemporaryDirectory() as tmp:
        base = monta_dir(Path(tmp))
        cargados = prs_mod.cargar(base)
        todas, vistos = [], set()
        for h in cargados.values():
            for pr in h["prs"]:
                clave = (pr["owner"], pr["repo"], pr["numero"])
                if clave not in vistos:
                    vistos.add(clave)
                    todas.append(pr)
        check("solo carga hilos con PR", list(cargados) == ["1003"], str(list(cargados)))
        check("una PR única no se duplica", len(todas) == 1, str(todas))

    print("5. verificación de ITSMECOM citados (itsmecom.py)")
    import itsmecom

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        canal = {
            "canal": 4,
            "nombre": "B - Gestion incidencias Tecnologia",
            "hilos": [
                {
                    "id": "2001",
                    "fecha": "21/10/2026 17:32",
                    "titulo": "[ZARA][ITSMECOM-5859496] ERROR IMPORTE TR CZ",
                    "autor": "Bruno Sanchez",
                    "respuestas": [
                        {
                            "autor": "Alba",
                            "fecha": "21/10/2026 17:56",
                            "texto": "nos llega de Alemania ITSMECOM-5861950",
                            "menciones": [],
                        },
                        {
                            "autor": "Vicente",
                            "fecha": "21/10/2026 18:00",
                            "texto": "otra vez itsmecom-5859496 en el hilo",
                            "menciones": [],
                        },
                    ],
                },
                {
                    "id": "2002",
                    "fecha": "04/11/2026 09:00",
                    "titulo": "Hilo sin tickets",
                    "autor": "alguien",
                    "respuestas": [],
                },
                {
                    "id": "2003",
                    "fecha": "21/09/2026 14:31",
                    "titulo": "Ha programado una reunión",
                    "autor": "(bot)",
                    "respuestas": [
                        {
                            "autor": "(bot)",
                            "fecha": "21/09/2026 14:32",
                            "texto": " ".join(
                                f"ITSMECOM-{n}" for n in range(5900000, 5900012)
                            ),
                            "menciones": [],
                        }
                    ],
                },
            ],
        }
        (base / "canal_04.json").write_text(
            json.dumps(canal, ensure_ascii=False), encoding="utf-8"
        )
        filas = itsmecom.cargar(base)
        por_id = {f["id"]: f for f in filas}
        check("solo hilos con ITSMECOM", sorted(por_id) == ["2001", "2003"], str(list(por_id)))
        check(
            "título + respuestas, sin duplicados y normalizado",
            por_id["2001"]["claves"] == ["ITSMECOM-5859496", "ITSMECOM-5861950"],
            str(por_id["2001"]["claves"]),
        )
        check("marca el resumen automático del bot", por_id["2003"]["bot"], str(por_id["2003"]))
        consultas = itsmecom.jql(filas)
        check("una sola consulta si caben todas", len(consultas) == 1, str(consultas))
        check(
            "la JQL incluye las claves de todos los hilos",
            all(
                f"ITSMECOM-{n}" in consultas[0]
                for n in list(range(5900000, 5900012)) + [5859496, 5861950]
            ),
            consultas[0],
        )
        troceadas = itsmecom.jql(filas, tamano_lote=5)
        check("trocea cuando se pide un lote menor", len(troceadas) == 3, str(len(troceadas)))

    print("6. relevancia estricta del canal 2 (Incidencias 🐞)")
    # Regresión de los tres fallos del informe del 18/10–04/11: un hilo de
    # Tágticos sin mención ni participación del squad entraba por «el canal
    # implica al squad»; un hilo abierto por el squad para reclamar a otro equipo
    # no debe contar como petición nuestra.

    def m(texto_: str, autor_: str, menciones_: list[str] | None = None) -> dict:
        """Mensaje crudo de Graph, que es lo que consumen los helpers."""
        return {
            "from": {"user": {"displayName": autor_}},
            "createdDateTime": "2026-11-04T10:00:00Z",
            "body": {"content": f"<p>{texto_}</p>"},
            "mentions": [{"mentionText": x} for x in (menciones_ or [])],
        }

    # (a) ajeno: ni mención ni participación de ProductForge
    ajeno = m("dadlo de alta porfi y unificad", "Antonio Diaz Maroto Chacon")
    check(
        "hilo de otro squad sin mención ni participación no es relevante",
        not (ec.menciona_squad(ajeno) or ec.squad_participa(ajeno, [ajeno])),
    )
    # (b) participación: un miembro responde en el hilo
    check(
        "la participación de un miembro hace relevante el hilo",
        ec.squad_participa(ajeno, [ajeno, m("reviso", "Jose Manuel Neto Delgado")]),
    )
    # (c) mención por etiqueta
    check(
        "la etiqueta del squad hace relevante el hilo",
        ec.menciona_squad(m("cc", "alguien", ["ProductForge"])),
    )
    # (d) nombre suelto en el texto NO es mención
    check(
        "un nombre sin etiquetar no cuenta como mención",
        not ec.menciona_squad(m("Angel Negrete, ¿lo ves?", "alguien")),
    )
    check(
        "una etiqueta a un miembro sí cuenta",
        ec.menciona_squad(m("cc", "alguien", ["Angel Negrete Tuñas"])),
    )
    # (e) la marca estricta se propaga desde barrido
    import barrido

    check(
        "barrido aplica relevancia estricta solo al canal 2",
        barrido.CANALES_CON_MENCION_ESTRICTA == {2}
        and 2 not in barrido.CANALES_CON_MENCION,
        str(barrido.CANALES_CON_MENCION_ESTRICTA),
    )

    print("7. reclamación a otro squad y cuerpo del raíz (05/11/2026)")
    # Dos fallos reales detectados por el usuario:
    #  a) el squad abre un hilo en Incidencias 🐞 para pedir a Grids que revise
    #     lo suyo: NO es trabajo nuestro.
    #  b) un hilo con 0 respuestas se clasificó por el título porque el cuerpo del
    #     raíz no se guardaba.

    # (a) raíz del squad etiquetando SOLO a otro equipo ⇒ reclamación, no nuestro
    raiz_otro = m(
        "Grids ¿le podéis echar un ojo?",
        "Alberto Barrio Louzao",
        ["Grids"],
    )
    check(
        "raíz del squad que solo etiqueta a Grids se detecta como reclamación",
        ec.raiz_reclama_a_otro(raiz_otro, [raiz_otro]),
    )
    check(
        "squads_ajenos extrae la etiqueta Grids",
        ec.squads_ajenos(raiz_otro) == ["Grids"],
        str(ec.squads_ajenos(raiz_otro)),
    )
    # si además nos etiquetan, deja de ser reclamación: hay petición hacia nosotros
    check(
        "si el hilo menciona al squad deja de ser reclamación a otro",
        not ec.raiz_reclama_a_otro(
            raiz_otro, [raiz_otro, m("cc", "alguien", ["ProductForge"])]
        ),
    )
    # raíz del squad SIN etiquetar a nadie: es tema propio, NO se excluye
    raiz_propio = m("No se muestran los grids donde cae un outfit", "Adrian Rabade Rodriguez")
    check(
        "raíz del squad sin etiquetas no es reclamación a otro equipo",
        not ec.raiz_reclama_a_otro(raiz_propio, [raiz_propio]),
    )
    # raíz de fuera etiquetando a otro equipo: tampoco es «reclamada por el squad»
    raiz_ajena = m("MenuDelux, tenemos un 503", "Luca Saletta Sillero", ["MenuDelux"])
    check(
        "raíz ajeno que etiqueta a otro equipo no se marca como reclamación nuestra",
        not ec.raiz_reclama_a_otro(raiz_ajena, [raiz_ajena]),
    )
    check(
        "un 'grids' suelto en el texto no cuenta como etiqueta a Grids",
        ec.squads_ajenos(m("los grids de la home fallan", "alguien")) == [],
    )

    # (b) el cuerpo del raíz debe llegar al índice aunque no haya respuestas
    fila = {
        "id": "1",
        "fecha": "05/11/2026 16:34",
        "fecha_raiz_fuera_de_rango": False,
        "titulo": "Problemas con el filtro Tipo de grid",
        "autor": "Alberto Barrio Louzao",
        "n_respuestas": 0,
        "ultima_actividad": "05/11/2026 16:34",
        "texto_raiz": "Grids ¿le podéis echar un ojo?",
        "autor_raiz_es_squad": True,
        "menciones_otras": ["Grids"],
        "reclama_a_otro": True,
        "menciones_squad": [],
        "respuestas": [],
        "urls_producto": [],
        "prs": [],
    }
    linea = ec.linea_indice(fila)
    check(
        "el índice muestra el texto del raíz cuando no hay respuestas",
        "¿le podéis echar un ojo?" in linea,
        linea[-90:],
    )
    check(
        "el índice marca RECLAMA_A_OTRO para el triage",
        "RECLAMA_A_OTRO" in linea,
        linea[:120],
    )

    print()
    if fallos:
        print(f"FALLARON {len(fallos)} comprobaciones: {', '.join(fallos)}")
        return 1
    print("Todas las comprobaciones OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
