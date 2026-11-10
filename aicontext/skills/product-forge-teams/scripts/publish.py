#!/usr/bin/env python3
"""Publica en Teams con el formato correcto (aviso de IA, negrita, cursiva, código).

Existe porque el conversor Markdown->HTML del paquete compartido
(`teams.util.text.markdown_to_html`) **no** soporta cursiva (`*x*`) ni code spans
(`` `x` ``): los deja literales, y el mensaje publicado muestra los asteriscos y
las comillas invertidas. Además el CLI `teams` no tiene comando para publicar un
mensaje **raíz** de canal (solo `channel reply`, que responde a un hilo existente),
así que sin este script hay que escribir a mano `app.graph._az.post(...)`.

Uso:
    # Hilo nuevo en un canal (mensaje raíz, con asunto)
    python3 publish.py root --team <TEAM> --channel <CH> --subject "<titulo>" \\
        --message-file msg.md [--dry-run]

    # Respuesta en un hilo existente
    python3 publish.py reply --team <TEAM> --channel <CH> --thread <ID> \\
        --message-file msg.md [--dry-run]

    # Chat (grupo o notas personales)
    python3 publish.py chat --chat <CHAT_ID> --message-file msg.md [--dry-run]

Opciones:
    --message-file <ruta>  fichero con el texto en Markdown (recomendado: evita
                           problemas de escapado en la shell)
    --message <texto>      alternativa a --message-file
    --subject <texto>      asunto del hilo (obligatorio en `root`, 10-15 palabras)
    --html                 el texto ya es HTML y se envía tal cual
    --dry-run              imprime el HTML resultante sin publicar
    --yes                  no pide confirmación interactiva

Soporta: **negrita**, *cursiva*, `código`, listas `- item`, listas numeradas
`N. item` (el primer número fija el inicio: <ol start="N">), enlaces
[texto](url), URLs sueltas y párrafos separados por línea en blanco.
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import sys
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

from teams.app import create_app  # noqa: E402
from teams.config import GRAPH_BETA  # noqa: E402

AVISO_IA = "🤖 Mensaje generado con IA"

# Marcadores internos para proteger el código inline del resto de conversiones.
_CODE_OPEN, _CODE_CLOSE = "\x00CODE\x00", "\x00/CODE\x00"


def _inline(texto: str) -> str:
    """Convierte los elementos inline de Markdown a HTML de Teams.

    El orden importa: el código inline se extrae primero (para que su contenido
    no se interprete como negrita/cursiva), luego enlaces, luego negrita y
    finalmente cursiva.
    """
    text = texto
    # 0) Escapar el texto de origen ANTES de generar etiquetas: si el mensaje
    #    trae `&`, `<` o `>`, sin esto romperían el HTML de Teams.
    text = html_lib.escape(text, quote=False)
    # 1) Código inline: `x` -> <code>x</code> (se protege con marcadores).
    text = re.sub(r"`([^`]+)`", _CODE_OPEN + r"\1" + _CODE_CLOSE, text)

    # 2) Enlaces [texto](url) antes que las URLs sueltas.
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # 3) Negrita **x** (antes que cursiva, si no `**x**` se parte).
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

    # 4) Cursiva *x*: no debe tocar los asteriscos ya consumidos por la negrita
    #    ni los que formen parte de una URL. Se exige que no haya `*` dentro.
    text = re.sub(r"(?<![\w*])\*([^*\n]+?)\*(?![\w*])", r"<i>\1</i>", text)

    # 5) URLs sueltas (sin tocar las que ya están en href="").
    text = re.sub(
        r'(?<!href=")(?<!">)(https?://[^\s<>"]+)',
        r'<a href="\1">\1</a>',
        text,
    )

    # 6) Restaurar el código inline.
    text = text.replace(_CODE_OPEN, "<code>").replace(_CODE_CLOSE, "</code>")
    return text


def markdown_to_teams_html(texto: str) -> str:
    """Convierte Markdown a HTML compatible con Teams.

    A diferencia de `teams.util.text.markdown_to_html`, soporta cursiva y código
    inline, que es justo lo que faltaba y provocaba que el aviso de IA saliera
    con asteriscos literales y los identificadores con backticks visibles.
    """
    if re.search(r"<(p|ul|ol|li|br|b|i|a|code|h[1-6])\b", texto, re.I):
        return texto  # ya es HTML

    partes: list[str] = []
    parrafo: list[str] = []
    en_lista: str | None = None  # "ul" | "ol" | None

    def cerrar_lista() -> None:
        nonlocal en_lista
        if en_lista:
            partes.append(f"</{en_lista}>")
            en_lista = None

    def cerrar_parrafo() -> None:
        if parrafo:
            partes.append(f"<p>{_inline(' '.join(parrafo))}</p>")
            parrafo.clear()

    for linea in texto.split("\n"):
        s = linea.strip()

        numerado = re.match(r"^(\d+)[.)]\s+(.+)$", s)
        if numerado:
            cerrar_parrafo()
            if en_lista != "ol":
                cerrar_lista()
                partes.append(f'<ol start="{int(numerado.group(1))}">')
                en_lista = "ol"
            partes.append(f"<li>{_inline(numerado.group(2))}</li>")
            continue

        vinyeta = re.match(r"^[-*+]\s+(.+)$", s)
        if vinyeta:
            cerrar_parrafo()
            if en_lista != "ul":
                cerrar_lista()
                partes.append("<ul>")
                en_lista = "ul"
            partes.append(f"<li>{_inline(vinyeta.group(1))}</li>")
            continue

        cerrar_lista()

        if not s:
            cerrar_parrafo()
            continue

        parrafo.append(s)

    cerrar_lista()
    cerrar_parrafo()

    return "\n".join(partes)


def _validar_entrada(texto: str) -> None:
    """Comprueba que el aviso de IA abre el mensaje."""
    if AVISO_IA not in texto:
        sys.exit(
            "ERROR: falta el aviso de IA. Todo mensaje debe empezar por "
            f"'{AVISO_IA}' (en cursiva)."
        )
    primera = next((l for l in texto.split("\n") if l.strip()), "")
    if AVISO_IA not in primera:
        sys.exit("ERROR: el aviso de IA debe ser la primera línea del mensaje.")


def _validar_salida(html: str) -> None:
    """Comprueba que la conversión no dejó Markdown sin procesar.

    Un backtick o un asterisco de énfasis en el HTML final significa que el
    mensaje se publicaría con la sintaxis a la vista, que es justo el fallo que
    este script evita.
    """
    problemas = []
    if "`" in html:
        problemas.append("backticks (código inline sin convertir)")
    if re.search(r"\*\*\S", html) or re.search(r"\S\*\*", html):
        problemas.append("negritas sin convertir (**)")
    if problemas:
        sys.exit(
            "ERROR: la conversión dejó sintaxis Markdown a la vista: "
            + ", ".join(problemas)
            + ".\nRevisa el mensaje; si el símbolo es literal, elimínalo del texto."
        )
    if AVISO_IA not in html_lib.unescape(re.sub(r"<[^>]+>", "", html)):
        sys.exit("ERROR: el aviso de IA se perdió en la conversión.")


def _leer_texto(args) -> str:
    if args.message_file:
        return Path(args.message_file).read_text(encoding="utf-8").strip()
    if args.message:
        return args.message.strip()
    sys.exit("ERROR: indica --message-file o --message.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def comunes(sp):
        sp.add_argument("--message-file", default=None)
        sp.add_argument("--message", default=None)
        sp.add_argument("--html", action="store_true", help="el texto ya es HTML")
        sp.add_argument("--dry-run", action="store_true")
        sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("root", help="Publica un mensaje raíz (hilo nuevo) en un canal")
    sp.add_argument("--team", required=True)
    sp.add_argument("--channel", required=True)
    sp.add_argument("--subject", required=True, help="Título del hilo (10-15 palabras)")
    comunes(sp)

    sp = sub.add_parser("reply", help="Responde en un hilo existente")
    sp.add_argument("--team", required=True)
    sp.add_argument("--channel", required=True)
    sp.add_argument("--thread", required=True)
    comunes(sp)

    sp = sub.add_parser("chat", help="Envía a un chat")
    sp.add_argument("--chat", required=True)
    comunes(sp)

    args = p.parse_args()

    texto = _leer_texto(args)
    if args.html:
        cuerpo = texto
    else:
        _validar_entrada(texto)
        cuerpo = markdown_to_teams_html(texto)
        _validar_salida(cuerpo)

    if args.dry_run:
        print("=== HTML a publicar ===")
        print(cuerpo)
        if getattr(args, "subject", None):
            print(f"\n=== subject ===\n{args.subject}")
        return

    app = create_app()

    if args.cmd == "root":
        url = f"{GRAPH_BETA}/teams/{args.team}/channels/{args.channel}/messages"
        data = app.graph._az.post(
            url,
            body={
                "subject": args.subject,
                "body": {"contentType": "html", "content": cuerpo},
            },
        )
        print(f"✓ Hilo publicado (id {data.get('id')}).")
        print(f"  {data.get('webUrl', '')}")

    elif args.cmd == "reply":
        msg_id = app.graph.reply_to_channel(args.team, args.channel, args.thread, cuerpo)
        print(f"✓ Respuesta publicada (id {msg_id}).")

    else:  # chat
        # OJO: `teams chat send` antepone "🤖 " si el mensaje no empieza por 🤖,
        # y con HTML eso inserta un emoji suelto antes del <p>. Aquí se envía el
        # HTML ya completo, sin ese prefijo.
        app.chat.send_message(args.chat, cuerpo)
        print("✓ Mensaje enviado al chat.")


if __name__ == "__main__":
    main()
