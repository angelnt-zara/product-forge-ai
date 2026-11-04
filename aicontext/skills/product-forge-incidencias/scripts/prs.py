#!/usr/bin/env python3
"""Estado de las PR enlazadas en los hilos, en UNA sola llamada a GitHub.

Motivo: la skill exigía aplicar la regla «hilo de externo con todas las PR
aprobadas ⇒ resuelto» y «hilo interno con todas las PR cerradas ⇒ omitir», pero
el flujo no consultaba las PR, así que esa regla no se aplicaba nunca. En el
informe del 18/10-04/11 eso publicó como pendiente un hilo cuya única petición
era aprobar una PR que ya estaba MERGED y APPROVED.

Coste medido: un lote de 40 PRs en una llamada GraphQL tarda ~1,7 s, casi lo
mismo que una de 5 (el coste es el proceso `gh`, no el número de PR), frente a
`gh pr view` por PR. Este script lee los JSON que ya dejó `barrido.py` (no llama
a Teams) y resuelve todas las PR de golpe.

Uso:
    python3 prs.py <dir_salida> [--json] [--hilos <id> ...]

Salida por defecto: una línea por PR con hilo, repo, número, estado y revisión.
Con --json: {id_hilo: [ {repo, numero, state, reviewDecision, title, url} ]}.

Requiere el CLI `gh` autenticado (mismo requisito que el resto del flujo).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# GraphQL: una sola petición con un alias por PR.
LOTE = 40


def cargar(dir_salida: Path) -> dict[str, dict]:
    """id de hilo -> fila, solo para los hilos que tienen PR."""
    por_id: dict[str, dict] = {}
    for fichero in sorted(dir_salida.glob("canal_*.json")):
        try:
            datos = json.loads(fichero.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"aviso: {fichero.name} ilegible ({exc})", file=sys.stderr)
            continue
        for h in datos.get("hilos") or []:
            if h.get("prs"):
                h["_canal"] = datos.get("canal")
                por_id[h["id"]] = h
    return por_id


def _consultar_lote(trozo: list[dict]) -> dict[tuple[str, str, int], dict] | None:
    """Una llamada GraphQL para un lote. None si falla.

    GraphQL es atómico: si UNA PR del lote no existe (borrada, número inválido)
    o su repo no es accesible, falla la respuesta entera. Por eso el llamador
    parte el lote y reintenta; aquí no se decide nada.
    """
    campos = []
    for i, pr in enumerate(trozo):
        campos.append(
            f'r{i}: repository(owner:"{pr["owner"]}", name:"{pr["repo"]}") '
            f'{{ pullRequest(number:{pr["numero"]}) '
            f'{{ number state reviewDecision title isDraft url }} }}'
        )
    q = "query {\n" + "\n".join(campos) + "\n}"
    try:
        r = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={q}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("aviso: gh api graphql agotó el tiempo", file=sys.stderr)
        return None
    if r.returncode != 0:
        return None
    try:
        datos = json.loads(r.stdout).get("data") or {}
    except json.JSONDecodeError:
        return None

    salida: dict[tuple[str, str, int], dict] = {}
    for i, pr in enumerate(trozo):
        nodo = ((datos.get(f"r{i}") or {}).get("pullRequest")) or {}
        if not nodo:
            continue
        salida[(pr["owner"], pr["repo"], pr["numero"])] = {
            "repo": f'{pr["owner"]}/{pr["repo"]}',
            "numero": pr["numero"],
            "state": nodo.get("state"),
            "reviewDecision": nodo.get("reviewDecision"),
            "title": nodo.get("title"),
            "isDraft": nodo.get("isDraft"),
            "url": nodo.get("url") or pr["url"],
        }
    return salida


def consulta(prs: list[dict]) -> dict[tuple[str, str, int], dict]:
    """Resuelve el estado de las PR con el menor número de llamadas posible.

    Si un lote falla se parte en dos y se reintenta, así una sola PR borrada
    cuesta unos pocos reintentos y no pierde el estado de las demás.
    """
    if not shutil.which("gh"):
        print(
            "aviso: no encuentro el CLI `gh`; no se resuelve el estado de las PR",
            file=sys.stderr,
        )
        return {}

    salida: dict[tuple[str, str, int], dict] = {}
    pendientes = [prs[i : i + LOTE] for i in range(0, len(prs), LOTE)]
    while pendientes:
        trozo = pendientes.pop()
        if not trozo:
            continue
        res = _consultar_lote(trozo)
        if res is not None:
            salida.update(res)
        elif len(trozo) > 1:
            medio = len(trozo) // 2
            pendientes.append(trozo[:medio])
            pendientes.append(trozo[medio:])
        else:
            pr = trozo[0]
            print(
                f"aviso: no se pudo resolver {pr['owner']}/{pr['repo']}"
                f"#{pr['numero']} (¿PR borrada o sin acceso?)",
                file=sys.stderr,
            )
    return salida


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("salida", help="directorio que dejó barrido.py")
    p.add_argument("--json", action="store_true", help="salida JSON por hilo")
    p.add_argument("--hilos", nargs="*", default=[], help="limita a estos ids")
    a = p.parse_args()

    salida = Path(a.salida)
    if not salida.is_dir():
        sys.exit(f"no existe el directorio: {salida}")

    por_id = cargar(salida)
    if a.hilos:
        pedidos = {x for bruto in a.hilos for x in bruto.replace(",", " ").split()}
        por_id = {k: v for k, v in por_id.items() if k in pedidos}

    todas: list[dict] = []
    vistos: set[tuple[str, str, int]] = set()
    for h in por_id.values():
        for pr in h["prs"]:
            clave = (pr["owner"], pr["repo"], pr["numero"])
            if clave not in vistos:
                vistos.add(clave)
                todas.append(pr)

    if not todas:
        if a.json:
            print("{}")
        else:
            print("No hay PR enlazadas en los hilos de este barrido.")
        return 0

    estado = consulta(todas)

    resultado: dict[str, list[dict]] = {}
    for i, h in por_id.items():
        filas = []
        for pr in h["prs"]:
            clave = (pr["owner"], pr["repo"], pr["numero"])
            info = estado.get(clave)
            if info:
                filas.append(info)
            else:
                # No se pudo consultar: se marca como desconocido para que el
                # agente lo muestre como limitación y NO aplique la regla de PR
                # cerrada.
                filas.append(
                    {
                        "repo": f'{pr["owner"]}/{pr["repo"]}',
                        "numero": pr["numero"],
                        "state": None,
                        "reviewDecision": None,
                        "title": None,
                        "isDraft": None,
                        "url": pr["url"],
                    }
                )
        resultado[i] = filas

    if a.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=1))
        return 0

    for i, filas in resultado.items():
        canal = por_id[i].get("_canal")
        print(f"\n{i} (canal {canal:02d}) · {por_id[i]['titulo'][:70]}")
        for f in filas:
            estado_txt = f["state"] or "DESCONOCIDO"
            revision = f["reviewDecision"] or "-"
            draft = " draft" if f["isDraft"] else ""
            print(
                f"  {f['repo']}#{f['numero']} · {estado_txt} · "
                f"{revision}{draft} · {f['url']}"
            )

    cerradas = sum(
        1
        for filas in resultado.values()
        if filas and all(f["state"] in ("MERGED", "CLOSED") for f in filas)
    )
    aprobadas = sum(
        1
        for filas in resultado.values()
        if filas and all(f["reviewDecision"] == "APPROVED" for f in filas)
    )
    print(
        f"\n{len(resultado)} hilos con PR · {cerradas} con todas cerradas · "
        f"{aprobadas} con todas aprobadas"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
