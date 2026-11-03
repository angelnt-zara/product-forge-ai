# Product Forge: temas pendientes (Teams + Jira)

Comando para obtener los temas pendientes del squad Products (Product Forge): hilos de Teams que mencionan al squad y tickets ITSMECOM abiertos. Opcionalmente, publica el resumen en Teams. Lo ejecuta el agente principal `product-forge-pana`, que **coordina** tres subagentes, **compone el informe** y **publica** en Teams.

Escanear y publicar son el mismo flujo: la publicación añade los pasos de borrador, confirmación y envío.

Los subagentes no comparten memoria: pásales todo el contexto que necesiten, incluida la norma de castellano. Intervienen `product-forge-incidencias-teams-extractor`, `product-forge-incidencias-jira-extractor` y `product-forge-incidencias-classifier`, indicados en cada paso del procedimiento; el resto de pasos son tuyos.

## Disparadores típicos

- Solo escaneo: "temas pendientes", "hilos sin responder", "escanea los canales", "ITSMECOM", "qué tenemos en Incidencias".
- Con publicación: "publica el resumen", "envíalo a la daily", "mándamelo al chat".

## Parámetros

- **Rango temporal**: por defecto últimos **7 días** sobre la creación del hilo (post raíz); las respuestas se leen completas aunque sean posteriores. El usuario puede indicar otro rango.
- **Canales**: todos por defecto; el usuario puede acotarlos.
- **PRs cerradas**: si incluir hilos con PR cerradas (por defecto no).
- **Publicar**: por defecto **no**. Solo se publica si el usuario lo pide en la petición o lo solicita tras ver el informe.
- **Destino** (solo si publica):
  - **Por defecto:** chat de grupo `19:c464808cd0a54e2ba8ee742d995f2341@thread.v2` (HTML directo). Es un chat con otras personas: indícalo en la confirmación.
  - **Hilo de la daily** en el canal «SQUAD Product Forge 🛠️», solo si lo pide.
  - **Chat privado del usuario** (`48:notes`), solo si lo pide expresamente.

Comandos, identificadores y cautelas de publicación están en la skill `product-forge-teams`.

## Procedimiento

1. **Alcance**: resuelve los parámetros anteriores y la **lista de miembros de ProductForge** (de `team.adoc`, según tus reglas comunes).
2. **Obtención en paralelo** (subagentes de solo lectura): lanza a la vez `product-forge-incidencias-teams-extractor` (hilos de Teams relevantes y sus respuestas, datos objetivos) y `product-forge-incidencias-jira-extractor` (ITSMECOM abiertos con todos sus comentarios, datos objetivos). Si ya hay datos recientes de esta sesión con el mismo alcance, reutilízalos. Si vas a publicar, pide también a `teams-extractor` los **informes previos** de los últimos 7 días (ver paso 7).
3. **Clasificación**: el `product-forge-incidencias-classifier` asigna criticidad, estado de atención, informativos y omisiones. Pásale los datos de ambos, la lista de miembros y si se incluyen PR cerradas. Si devuelve **solicitudes de aclaración**, trasládalas al subagente correspondiente (`teams-extractor` o `jira-extractor`, reutilizando su sesión) y devuelve la respuesta al clasificador. Itera hasta que no queden dudas relevantes.
4. **Cotejo (obligatorio, tuyo):** antes de presentar o redactar nada, revisa la clasificación elemento a elemento y corrige o devuelve al clasificador lo que incumpla estas reglas:
   - Consultas ITSMECOM (Solicitud de servicio): solo 🟡 o ⚪.
   - PRE y entornos previos: solo 🟡 o ⚪, también en incidentes.
   - Incidentes: como mínimo 🟠 (salvo el tope de PRE).
   - Nada ya corregido/resuelto en Jira marcado 🔴 sin justificarlo.
   - Coherencia con clasificaciones previas de la sesión para el mismo hilo o ticket.
   - Las limitaciones y la cobertura de los subagentes de lectura (rango cubierto, canales inaccesibles, miembros no verificados) se muestran al usuario.
   Las decisiones relevantes o dudosas son tuyas: si no puedes decidir, pregunta al usuario con `question`.
5. **Presentación (informe mínimo)**: compón el informe según «Formato del informe» y muéstralo. Ampliar contexto solo si el usuario lo pide (vuelve a delegar el hilo/ticket concreto).
6. **Si no se publica**: termina ofreciendo ampliar contexto o publicar el resumen, sin más texto.
7. **Si se publica** (acción que modifica estado):
   1. Con los informes previos devueltos por `teams-extractor`, aplica las reglas de «Informes previos» y compón el **borrador** según «Mensaje de publicación», con validación regex. Indica al usuario cuántos resueltos se han omitido.
   2. Muestra al usuario el borrador tal y como se verá en Teams y el **destino exacto**, y pide confirmación con `question`. Cada versión nueva requiere una confirmación nueva.
   3. Solo con un "sí" claro, **publica tú** el texto exacto confirmado en el destino (skill `product-forge-teams`), tras volver a validarlo con la regex. No permitas que el texto cambie entre borrador y envío.
   4. Informa del resultado. Recuerda que los mensajes enviados no se pueden editar ni borrar.

## Formato del informe (escaneo)

**Por defecto el informe es mínimo.** El contexto se da solo si el usuario lo pide. No muestres preview largo ni explicaciones no solicitadas.

Cada hilo o ticket lleva **dos emojis**, siempre **los primeros de cada viñeta** y en este orden: 1º criticidad (🔴 urgente, 🟠 importante, 🟡 baja, ⚪ nula), 2º atendido (🫥 no atendido, 🏃‍♂️‍➡️ atendido en curso, ✅ resuelto).

1. Una línea de alcance: canales, rango, zona horaria (`Europe/Madrid`) y nº de hilos relevantes.
2. Tabla resumen por canal (relevantes / por criticidad 🔴 🟠 🟡 ⚪ / por atención 🫥 🏃‍♂️‍➡️ ✅ / informativos / omitidos), solo con los canales con actividad.
3. **Pendientes (🫥 y 🏃‍♂️‍➡️)**, ordenados según «Orden», **una sola línea por elemento**: criticidad + atendido · fecha · antigüedad · canal · autor · tema en pocas palabras · URL completa en texto visible. Marca con «(PR abierta)» los hilos del equipo. Separa hilos de Teams, incidencias ITSMECOM y consultas ITSMECOM.
4. No listes por defecto resueltos (✅), informativos, motivos ni observaciones. Añade una única línea final «Omitidos: N resueltos, N informativos, N PR cerradas» y avisa solo de limitaciones que afecten al resultado (canal inaccesible, miembros no verificados, truncado).

**Orden dentro de cada bloque** (informe y mensaje): primero por criticidad (🔴, 🟠, 🟡, ⚪) y, dentro de la misma, por atendido (🫥, 🏃‍♂️‍➡️, ✅). A igualdad de ambos, del más antiguo al más reciente.

## Mensaje de publicación (borrador y envío)

- **Primera línea (título)**: `**Temas pendientes entre dd/mm/aaaa y dd/mm/aaaa**` con la fecha de inicio y fin del informe, seguida de línea en blanco. Es la única línea que no es viñeta ni cabecera de bloque. Va después del aviso de IA obligatorio (skill `product-forge-teams`).
- Mensaje **conciso**: pendientes (🫥 y 🏃‍♂️‍➡️) en los bloques 1 a 4; los ✅ solo en el 5º bloque, iniciados por personas externas.
- **Un tema por línea**, como viñeta, con las particularidades de formato de `product-forge-teams`.
- **Cinco bloques**, en este orden, cada uno ordenado según «Orden» y omitido si está vacío: 1º «Hilos abiertos por personas externas» (🫥/🏃‍♂️‍➡️ de Teams); 2º «Incidencias ITSMECOM»; 3º «Consultas ITSMECOM»; 4º «Hilos internos» (hilos del equipo con PR abierta); 5º «Hilos externos resueltos» (✅ iniciados por personas externas).
- **Formato de línea ITSMECOM**: `- <criticidad> <atendido> [ITSMECOM-N](https://jira.inditex.com/jira/browse/ITSMECOM-N): <título> · dd/mm — <descripción>`. **El enlace va solo sobre el ID**. Atendido: 🫥 (En Cartera, sin asignar) o 🏃‍♂️‍➡️ (asignado y En Curso); fecha de creación. Quita `[` y `]` del título.
- **Estado ITSMECOM**: en los En Curso indica «En curso, asignado a <nombre>»; en los En Cartera «En cartera, sin asignar».
- **Descripción ITSMECOM obligatoria** en todos: breve, del problema, sacada de los últimos comentarios (o de la descripción si no hay). Sin corchetes ni datos inventados.
- **Hilos de Teams**: el **enlace va sobre el título** (`[título](webUrl)`), seguido de `· dd/mm`, con los dos emojis al inicio. En hilos del equipo, el texto es el título de la PR (`gh pr view`), la principal si hay varias.
- **Canal en el 1er bloque**: cada línea empieza por el nombre completo del canal dentro del texto del enlace: `- <criticidad> <atendido> [<Canal>: <título>](url) · dd/mm` (y ` — <resumen>` en los 🏃‍♂️‍➡️). Sin sufijo «Canal …».
- **Resumen de estado**: en TODOS los hilos 🏃‍♂️‍➡️ y ✅ añade tras la fecha ` — <resumen breve>`: la solución en los resueltos y lo que queda pendiente en los de seguimiento. Sin corchetes. Los 🫥 no llevan resumen.
- **Sin duplicados**: cada hilo o ticket aparece una sola vez.
- **Texto sin corchetes ni truncados.** Mantén una única fuente del texto.
- **Comprobación previa al envío**: valida con regex que cada línea de viñeta sea `- <criticidad> <atendido> [<texto sin corchetes>](<url>) · dd/mm`, por ejemplo `^- (🔴|🟠|🟡|⚪) (🏃‍♂️‍➡️|🫥|✅) \[[^\[\]]+\]\(https://[^)\s]+\)(: [^\[\]]+?)? · \d\d/\d\d( — [^\[\]]+)?$`, y no envíes si alguna falla.
- Sin línea de «Urgente» ni texto adicional. Avisa de que los mensajes enviados no se pueden editar ni borrar.

### Informes previos

Con los informes `Temas pendientes entre …` de los últimos 7 días que devuelve `teams-extractor`, **omite del 5º bloque los ✅ que ya aparezcan como resueltos** en alguno (identifícalos por `webUrl`/clave). Los hilos todavía abiertos (🫥/🏃‍♂️‍➡️, incluidos ITSMECOM) **se incluyen siempre**, y un hilo que antes estaba pendiente y ahora está resuelto se incluye como resuelto. Si el 5º bloque queda vacío, omítelo. Informa al usuario de cuántos se han omitido y de qué mensaje(s), o de que no había informe previo. Si `teams` no pudo leer el hilo, indícalo como limitación y no omitas nada.

## Reglas

- Responde siempre en castellano y pásaselo explícitamente a los subagentes.
- Horas siempre en `Europe/Madrid`, nunca en UTC.
- No inventes hilos, tickets, autores ni fechas: todo sale de lo que devuelvan los subagentes. Muestra sus limitaciones.
- Los subagentes son de solo lectura; la publicación la haces tú, solo con confirmación explícita.
