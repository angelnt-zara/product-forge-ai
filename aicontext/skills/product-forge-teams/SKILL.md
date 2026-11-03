---
name: product-forge-teams
description: Cómo leer y publicar mensajes en Teams para el squad Product Forge (Pacman Products) con el CLI `teams`. Incluye destinos de publicación del squad, comandos de lectura/publicación y particularidades de formato (Markdown/HTML). Úsala en cualquier flujo que lea canales de Teams o publique en la daily o en el chat privado.
---

# Product Forge: interacción con Teams

Referencia técnica reutilizable para leer y publicar en Teams. No contiene criterios de negocio (qué hilos son relevantes, clasificación, contenido del resumen): eso es de cada flujo que la use.

Si falla la autenticación de Teams/Graph (`az login`, token expirado, permisos), indícalo y remite a la skill `teams-setup`; es válido para cualquier agente o subagente que use esta skill. Las skills base `teams-channels` y `teams-setup` aportan el CLI; esta skill añade el contexto del squad.

## Reglas obligatorias de todo mensaje publicado

Aplican SIEMPRE, en cualquier flujo que use esta skill y sea cual sea el destino:

- **Aviso de IA:** TODO mensaje que se publique en Teams (respuesta en canal, hilo nuevo, chat privado o cualquier otro destino) empieza por la línea `🤖 Mensaje generado con IA` **en cursiva** (Markdown: `*🤖 Mensaje generado con IA*`), para advertir al lector de que lo ha generado un agente. Va siempre **al principio**, antes de cualquier título o contenido, separada del resto por una línea en blanco (en HTML, como `<p><i>🤖 Mensaje generado con IA</i></p>`). Forma parte del texto exacto que se muestra al usuario y que este confirma; no la omitas ni la modifiques.
- **Título en hilos nuevos:** si el mensaje **abre un hilo nuevo** (no es una respuesta), debe incluir siempre un título que resuma la petición o el problema en un **máximo de 10-15 palabras**. Si el CLI admite asunto (`subject`), úsalo; si no, es la primera línea en negrita tras el aviso de IA. Las respuestas a hilos existentes no necesitan título adicional.

## Lectura

CLI desde la raíz del runtime. Requiere `az login`:

```bash
export PYTHONPATH="$PWD/.opencode/skills/_shared/scripts"
python3 -m teams channel messages --team <GROUP_ID> --channel "<CHANNEL_ID>" --top 50 --pages 4 --json \
  | jq --arg since "<ISO, p. ej. 2026-10-18T00:00:00Z>" '[.[] | select(.messageType=="message" and .createdDateTime >= $since)]'
python3 -m teams channel replies  --team <GROUP_ID> --channel "<CHANNEL_ID>" --thread <MESSAGE_ID> --json
```

- **No uses `--since` en `channel messages`:** la API de canales lo rechaza con error 400. Lee con `--top`/`--pages` suficientes y **filtra por fecha en local** (campo de creación del mensaje raíz). Comprueba que el mensaje más antiguo leído es anterior al inicio del rango; si no, itera más páginas.
- **No leas más páginas de las necesarias:** el CLI solo admite `--pages N` (no hay `--skip`: cada llamada relee desde el principio). Empieza con `--pages 2` y, si el mensaje más antiguo leído sigue dentro del rango, repite ese canal con `--pages 4` y luego `--pages 8`, y así hasta cubrirlo; no uses un número fijo de páginas por canal. Un canal con pocos mensajes en el rango no debe pagar la lectura de uno de mucho volumen. **Excepción:** el canal «SQUAD Product Forge 🛠️» (alto volumen, ~400 mensajes en 16 días) se lee directamente con `--pages 8`, sin escalera, para no releer lo mismo varias veces; si con 8 páginas el mensaje más antiguo sigue dentro del rango, avísalo como limitación.
- **Filtra con `jq` antes de volcar contenido al contexto:** de cada página conserva solo los mensajes raíz con `createdDateTime` dentro del rango (más los campos mínimos: `id`, `webUrl`, `from`, `mentions`, fecha y cuerpo) y, en los canales que filtran por mención, descarta ya en `jq` los raíz sin mención relevante (salvo que sus respuestas puedan contenerla). Lee `replies` solo de los hilos cuyo post raíz esté en el rango.
- **Paraleliza las lecturas por hilo y por PR:** lanza las llamadas `channel replies` de todos los hilos en el mismo bloque (en paralelo), no una a una. La consulta de las PR se paraleliza igual (ver skill `product-forge-github`).
- Usa siempre `--json` para poder inspeccionar `mentions`, `from`, `replyToId`, `webUrl` y fechas. En `mentions`, el nombre de una etiqueta aparece en `mentionText`.
- Los canales son independientes: consúltalos **en paralelo** (varias llamadas en el mismo bloque, o subagentes `general` si el volumen es grande).
- Si un canal devuelve el máximo de páginas, es una limitación: avísalo e itera más páginas.
- Ignora mensajes de sistema, eventos de unión/salida de canal, eventos/grabaciones de reuniones y mensajes eliminados.
- Las fechas vienen en UTC: conviértelas a `Europe/Madrid` al mostrarlas.
- El hilo de la daily (mensaje raíz `1789993863727`) devuelve como máximo 50 respuestas, casi todas eventos de sistema: no sirve para analizar temas, pero sí para localizar mensajes ya publicados (p. ej. informes anteriores del agente). Filtra por texto y por fecha; si el máximo de 50 puede dejar fuera mensajes del rango pedido, indícalo como limitación.

## Publicación

Modifica estado y **no se puede editar ni borrar lo enviado**. Solo se publica con el **texto exacto**, el **destino** y la **confirmación explícita** del usuario (cada versión nueva requiere una confirmación nueva). Envía exactamente el texto confirmado.

### Destinos

- **Chat de grupo por defecto** (destino por defecto, definido por el usuario el 03/11/2026): chat `19:c464808cd0a54e2ba8ee742d995f2341@thread.v2` («[INCIDENCIAS] Product Forge 🛠️»). Es un chat con otros miembros (p. ej. Jose Manuel Neto Delgado y Francisco Javier Corchado Bernal), no unas notas personales: indica siempre este destino en la confirmación. Se envía como **HTML directo** (ver «Formato del mensaje»):

  ```bash
  python3 -m teams chat send --chat "19:c464808cd0a54e2ba8ee742d995f2341@thread.v2" --message "<html>" --yes
  ```

- **Hilo de la daily** (solo si el usuario lo pide): canal «SQUAD Product Forge 🛠️», mensaje raíz `1789993863727`. Se envía como respuesta (Markdown):

  ```bash
  python3 -m teams channel reply --team 1301738f-827e-48ec-8770-3f0922c1c295 --channel "19:c2d93e0c05834c5f885f7ebbb2a82da8@thread.tacv2" --thread 1789993863727 --message "<md>" --yes
  ```

  Ya no se publica en el chat de grupo «Product Forge 🛠️».
- **Chat privado del usuario** (solo si lo pide expresamente): el chat de notas personales `48:notes`.

  ```bash
  python3 -m teams chat send --chat "48:notes" --message "<html>" --yes
  ```

  **No uses el 1:1 que `chat list` muestra como «Chat with <nombre del usuario>»**: puede ser el de otra persona (ya se envió por error a Vicente Vidal Aznar). Antes de enviar a cualquier chat 1:1, verifica el destinatario real leyendo `chat messages`, e indica el chat exacto en la confirmación.

### Formato del mensaje

- **Markdown (respuesta en canal):** el conversor une con espacios las líneas consecutivas que no sean viñetas. Escribe cada viñeta (`- `) precedida de una línea en blanco.
- **Corchetes prohibidos en el texto del enlace:** `[` y `]` dentro de `[texto](url)` rompen el Markdown y el enlace sale como URL cruda. Reemplaza `[PACMAN-NNN] título` por `PACMAN-NNN: título`, elimina cualquier otro `[` o `]` (y `(` `)` sin balancear) y no uses títulos truncados con `…`.
- **Espaciado entre bloques:** el conversor Markdown→HTML no deja espacio visible entre bloques (ni líneas en blanco ni párrafos con `&nbsp;`). Para el chat privado, envía **HTML directo** (si el mensaje contiene HTML se envía tal cual): títulos y cabeceras en `<p><b>…</b></p>`, viñetas en `<ul><li>…</li></ul>`, enlaces con `<a href="…">` (con `&amp;` en la URL) y un `<br>` extra antes de cada cabecera de bloque, incluida la que sigue al título.
- **Una única fuente del texto** para que el borrador mostrado al usuario y lo enviado coincidan. El borrador se muestra como se vería en Teams (enlaces sobre el texto, sin URLs); si se pide el literal, con las URLs completas.
- Valida el formato del mensaje (p. ej. con regex por línea) antes de enviar y no envíes si alguna línea falla.
