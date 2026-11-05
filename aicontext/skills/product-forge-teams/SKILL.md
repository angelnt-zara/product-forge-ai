---
name: product-forge-teams
description: Cómo leer y publicar mensajes en Teams para el squad Product Forge (Pacman Products) con el CLI `teams`. Incluye destinos de publicación del squad, comandos de lectura/publicación y particularidades de formato (Markdown/HTML). Úsala en cualquier flujo que lea canales de Teams o publique en la daily o en el chat privado.
---

# Product Forge: interacción con Teams

Referencia técnica reutilizable para leer y publicar en Teams. No contiene criterios de negocio (qué hilos son relevantes, clasificación, contenido del resumen): eso es de cada flujo que la use.

Si falla la autenticación de Teams/Graph (`az login`, token expirado, permisos), indícalo y remite a la skill `/teams-setup`; es válido para cualquier agente o subagente que use esta skill. Las skills base `/teams-channels` y `/teams-setup` aportan el CLI; esta skill añade el contexto del squad.

## Reglas obligatorias de todo mensaje publicado

Aplican SIEMPRE, en cualquier flujo que use esta skill y sea cual sea el destino:

- **Aviso de IA:** TODO mensaje que se publique en Teams (respuesta en canal, hilo nuevo, chat privado o cualquier otro destino) empieza por la línea `🤖 Mensaje generado con IA` **en cursiva** (Markdown: `*🤖 Mensaje generado con IA*`), para advertir al lector de que lo ha generado un agente. Va siempre **al principio**, antes de cualquier título o contenido, separada del resto por una línea en blanco. Forma parte del texto exacto que se muestra al usuario y que este confirma; no la omitas ni la modifiques. `publish.py` la exige y aborta si falta.
- **Título en hilos nuevos:** si el mensaje **abre un hilo nuevo** (no es una respuesta), debe incluir siempre un título que resuma la petición o el problema en un **máximo de 10-15 palabras**. Va en el `subject` del mensaje raíz (`publish.py root --subject`), no como primera línea en negrita. Las respuestas a hilos existentes no necesitan título adicional.

## Lectura

**Vía preferente para canales completos: `extract_channel.py`.** Para leer un canal entero (raíces de un rango + respuestas completas) usa el script de la skill `/product-forge-incidencias`, que pagina de verdad y evita el bucle de escribir un extractor a mano:

```bash
python3 .opencode/skills/product-forge-incidencias/scripts/extract_channel.py \
  "<GROUP_ID>" "<CHANNEL_ID>" "<desde_iso>" [--solo-storefront|--sin-filtro|--regex …] \
  [--desde-ultima-actividad] [--json]
```

Motivo: `python3 -m teams channel replies` devuelve **como máximo 50 respuestas y no sigue `@odata.nextLink`** (el método `channel_thread` del paquete compartido hace un único `GET`). El script sí pagina, así que un hilo de 230 respuestas llega completo en ~3 s. Medido: un canal de implantación pasó de ~29 minutos a 17–40 segundos.

**CLI de respaldo.** El resto de comandos de esta sección sirven para lecturas puntuales (un hilo concreto, informes previos, chats) y como respaldo si el script no está disponible. Requiere `az login`:

```bash
export PYTHONPATH="$PWD/.opencode/skills/_shared/scripts"
python3 -m teams channel messages --team <GROUP_ID> --channel "<CHANNEL_ID>" --top 50 --pages 4 --json \
  | jq --arg since "<ISO, p. ej. 2026-10-18T00:00:00Z>" '[.[] | select(.messageType=="message" and .createdDateTime >= $since)]'
python3 -m teams channel replies  --team <GROUP_ID> --channel "<CHANNEL_ID>" --thread <MESSAGE_ID> --json
```

Cada llamada se hace **a un solo canal**. Los canales se leen en paralelo, cada uno en su propia invocación; nunca se agrupan varios canales en el mismo proceso de lectura.

- **Comprueba el rango con el criterio de parada correcto:** no uses el mensaje más antiguo leído (hay mensajes anómalos de fechas muy antiguas o nuevas dentro de la lista, p. ej. un mensaje de 2025 en la posición ~24 del canal «SQUAD Product Forge 🛠️»). El rango está cubierto cuando hay **mensajes raíz consecutivos anteriores al inicio del rango** (ignora outliers aislados). Si no, itera más páginas. No uses `--since` en `channel messages`: la API de canales lo rechaza con error 400; lee con `--top`/`--pages` y **filtra por fecha en local** (campo de creación del mensaje raíz).
- **No leas más páginas de las necesarias:** el CLI solo admite `--pages N` (no hay `--skip`: cada llamada relee desde el principio). Empieza con `--pages 2` en todos los canales, incluido «SQUAD Product Forge 🛠️» (en un rango de 7 días ~25 mensajes raíz, cubiertos con 1 página) y, si el criterio de parada anterior no se cumple, repite ese canal con `--pages 4` y luego `--pages 8`, y así hasta cubrirlo. No uses un número fijo de páginas por canal; si con 8 páginas el rango sigue sin cubrirse, avísalo como limitación. Ojo con los canales de mucho tráfico (los de soporte de API e implantación por cadena del flujo de incidencias): ahí es normal necesitar 4 u 8 páginas, y pueden aparecer mensajes raíz con fechas muy anteriores intercaladas que hay que tratar como outliers y no como criterio de parada.
- **Filtra con `jq` antes de volcar contenido al contexto:** de cada página conserva solo los mensajes raíz con `createdDateTime` dentro del rango (más los campos mínimos: `id`, `webUrl`, `from`, `mentions`, fecha y cuerpo) y, en los canales que filtran por mención, descarta ya en `jq` los raíz sin mención relevante (salvo que sus respuestas puedan contenerla). Lee `replies` solo de los hilos cuyo post raíz esté en el rango.
- **Paraleliza las lecturas por hilo y por PR:** lanza las llamadas `channel replies` de todos los hilos en el mismo bloque (en paralelo), no una a una. La consulta de las PR se paraleliza igual (ver skill `/product-forge-github`). En shell, usa concurrencia acotada a **8 procesos** contra Graph. Medido sobre este CLI: 4 hilos tardan 6,6 s en serie y 1,5 s con `-P 8`; con 40 hilos, `-P 8` tarda 7,8 s y `-P 24` tarda 11,0 s (más procesos no acelera: hay contención y riesgo de 429/503). El script `extract_channel.py` usa 16 workers en su lugar (`--workers`, o la variable `PF_TEAMS_WORKERS`), porque pagina él mismo y absorbe los 429 con reintento; medido, 16 workers baten a 8 en el barrido de hilos antiguos. Ejemplo para un canal ya listado en `hilos.txt` (un `rootId` por línea):

  ```bash
  mkdir -p out
  xargs -P 8 -I{} sh -c 'python3 -m teams channel replies --team "$TEAM" --channel "$CH" --thread {} --json > out/{}.json 2> out/{}.err' < hilos.txt
  ```

  Después procesa los `out/*.json` en local con `jq` (una sola pasada, sin volver a llamar a la API). Comprueba los `.err` no vacíos y relanza **solo** esos hilos, en serie o con `-P 2`: un `.err` no vacío es «respuestas no leídas», nunca «sin respuestas».
- Usa siempre `--json` para poder inspeccionar `mentions`, `from`, `replyToId`, `webUrl` y fechas. En `mentions`, el nombre de una etiqueta aparece en `mentionText`.
- **Formato de `channel replies --json`:** devuelve un **objeto** `{parent, replies[]}`, no un array. Los filtros `jq` deben apuntar a `.replies[]` (un filtro que asuma array falla con `Cannot index array`). Inspecciona la salida real antes de filtrar y, si un filtro falla, reintenta sin filtro; un fallo de lectura nunca equivale a «sin respuestas». **Recuerda que esta llamada corta en 50 respuestas**: si el hilo tiene más, usa el script.
- Si un canal devuelve el máximo de páginas, es una limitación: avísalo e itera más páginas.
- Ignora mensajes de sistema, eventos de unión/salida de canal, eventos/grabaciones de reuniones y mensajes eliminados.
- Las fechas vienen en UTC: conviértelas a `Europe/Madrid` al mostrarlas.
- El hilo de la daily (mensaje raíz `1789993863727`) devuelve como máximo 50 respuestas, casi todas eventos de sistema: no sirve para analizar temas, pero sí para localizar mensajes ya publicados (p. ej. informes anteriores del agente). Filtra por texto y por fecha; si el máximo de 50 puede dejar fuera mensajes del rango pedido, indícalo como limitación.

## Publicación

Modifica estado y **no se puede editar ni borrar lo enviado**. Solo se publica con el **texto exacto**, el **destino** y la **confirmación explícita** del usuario (cada versión nueva requiere una confirmación nueva). Envía exactamente el texto confirmado.

**Publica siempre con `scripts/publish.py`, no con el CLI directo.** Motivo: el conversor Markdown→HTML del paquete compartido (`teams.util.text.markdown_to_html`, que es lo que usan `teams channel reply` y `teams chat send`) **no soporta cursiva ni código inline**: `*texto*` y `` `texto` `` salen con los asteriscos y los backticks a la vista. Consecuencia real observada el 05/11/2026 en «Incidencias 🐞»: el aviso de IA se publicó como `*🤖 Mensaje generado con IA*` literal y los identificadores (`COMING_SOON_CHANGED`, `MilestoneNotFoundException`) con las comillas invertidas visibles. Además, el CLI **no tiene comando para publicar un mensaje raíz** de canal (solo `channel reply`), así que un hilo nuevo obliga a escribir código a mano.

```bash
# Hilo nuevo (mensaje raíz, con asunto)
python3 .opencode/skills/product-forge-teams/scripts/publish.py root \
  --team <GROUP_ID> --channel "<CHANNEL_ID>" --subject "<título>" \
  --message-file /tmp/msg.md

# Respuesta en un hilo existente
python3 .opencode/skills/product-forge-teams/scripts/publish.py reply \
  --team <GROUP_ID> --channel "<CHANNEL_ID>" --thread <MESSAGE_ID> \
  --message-file /tmp/msg.md

# Chat (grupo o notas personales)
python3 .opencode/skills/product-forge-teams/scripts/publish.py chat \
  --chat <CHAT_ID> --message-file /tmp/msg.md
```

- **Escribe siempre el mensaje en un fichero** (`--message-file`) y pásalo al script: evita problemas de escapado en la shell con asteriscos, backticks y comillas. Muestra al usuario **ese mismo fichero** como borrador.
- **`--dry-run` antes de publicar**: imprime el HTML resultante sin enviar nada. Úsalo para comprobar que la cursiva y el código salen como etiquetas y no como texto.
- El script **valida** el mensaje: exige que el aviso de IA abra el texto y aborta si la conversión deja backticks o `**` a la vista.
- El script **escapa** `&`, `<` y `>` antes de generar etiquetas, así que el texto puede llevarlos sin romper el HTML.
- `--html` envía el texto tal cual (ya convertido). Resérvalo para casos en que el HTML esté escrito a mano y validado.

### Destinos

- **Chat de grupo por defecto** (destino por defecto, definido por el usuario el 03/11/2026): chat `19:c464808cd0a54e2ba8ee742d995f2341@thread.v2` («[INCIDENCIAS] Product Forge 🛠️»). Es un chat con otros miembros (p. ej. Jose Manuel Neto Delgado y Francisco Javier Corchado Bernal), no unas notas personales: indica siempre este destino en la confirmación.

  ```bash
  python3 .opencode/skills/product-forge-teams/scripts/publish.py chat \
    --chat "19:c464808cd0a54e2ba8ee742d995f2341@thread.v2" --message-file /tmp/msg.md
  ```

  No uses `teams chat send` con HTML: antepone un `🤖` suelto al mensaje cuando el texto no empieza por ese emoji, y con HTML queda un emoji huérfano antes del primer párrafo.

- **Hilo de la daily** (solo si el usuario lo pide): canal «SQUAD Product Forge 🛠️», mensaje raíz `1789993863727`. Se envía como respuesta:

  ```bash
  python3 .opencode/skills/product-forge-teams/scripts/publish.py reply \
    --team 1301738f-827e-48ec-8770-3f0922c1c295 \
    --channel "19:c2d93e0c05834c5f885f7ebbb2a82da8@thread.tacv2" \
    --thread 1789993863727 --message-file /tmp/msg.md
  ```

  Ya no se publica en el chat de grupo «Product Forge 🛠️».
- **Chat privado del usuario** (solo si lo pide expresamente): el chat de notas personales `48:notes`.

  ```bash
  python3 .opencode/skills/product-forge-teams/scripts/publish.py chat --chat "48:notes" --message-file /tmp/msg.md
  ```

  **No uses el 1:1 que `chat list` muestra como «Chat with <nombre del usuario>»**: puede ser el de otra persona (ya se envió por error a Vicente Vidal Aznar). Antes de enviar a cualquier chat 1:1, verifica el destinatario real leyendo `chat messages`, e indica el chat exacto en la confirmación.

- **Hilo nuevo en un canal** (p. ej. escalado a otro squad, ver `/product-forge-pacman-kos`): usa `publish.py root` con `--subject`. El asunto es obligatorio y va en el `subject` del mensaje raíz, no como primera línea en negrita. El canal y su `groupId`/`channelId` los determina el flujo que publica; esta skill solo resuelve el mecanismo.

### Formato del mensaje

- **Sintaxis admitida por `publish.py`:** `**negrita**`, `*cursiva*`, `` `código` ``, viñetas `- item`, enlaces `[texto](url)`, URLs sueltas y párrafos separados por línea en blanco. Es lo único que se convierte; no uses tablas, encabezados `#` ni bloques de código con triple backtick.
- **Aviso de IA:** la primera línea, `*🤖 Mensaje generado con IA*`, es obligatoria y el script aborta si no está o no abre el mensaje.
- **El conversor del CLI no sirve para esto:** `teams channel reply` y `teams chat send` usan `markdown_to_html` del paquete compartido, que **no** interpreta `*cursiva*` ni `` `código` `` (los deja literales). No publiques con esos comandos: usa `publish.py`.
- **Líneas consecutivas sin viñeta** se unen en un mismo párrafo, separadas por un espacio. Para forzar un salto, deja una línea en blanco.
- **Corchetes prohibidos en el texto del enlace:** `[` y `]` dentro de `[texto](url)` rompen el Markdown y el enlace sale como URL cruda. Reemplaza `[PACMAN-NNN] título` por `PACMAN-NNN: título`, elimina cualquier otro `[` o `]` (y `(` `)` sin balancear) y no uses títulos truncados con `…`.
- **`&`, `<` y `>`** se escapan solos; puedes escribirlos en el texto.
- **Una única fuente del texto** para que el borrador mostrado al usuario y lo enviado coincidan: el fichero `--message-file`. El borrador se muestra como se vería en Teams (enlaces sobre el texto, sin URLs); si se pide el literal, con las URLs completas.
- **Comprueba con `--dry-run`** el HTML antes de publicar. Valida que no queden backticks ni `**` a la vista.
