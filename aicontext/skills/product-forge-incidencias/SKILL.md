---
name: product-forge-incidencias
description: Flujo de temas pendientes del squad Products Forge.
---

# Product Forge: incidencias pendientes (Teams + Jira)

> **Invocación explícita obligatoria:** esta skill solo se ejecuta cuando el usuario la pide de forma explícita. No la cargues ni ejecutes por inferencia, por coincidencia con la descripción ni desde otra skill o subagente. Si dudas de que la petición sea explícita, pregunta antes con la herramienta `question`.

Flujo para obtener los temas pendientes del squad Products (Product Forge): hilos de Teams que mencionan al squad —incluidos los canales de soporte de API Storefront y de implantación por cadena, filtrados por mención a Storefront y URL de API de Producto— y tickets ITSMECOM abiertos. Opcionalmente, publica el resumen en Teams. Lo ejecuta el agente principal `product-forge-pana`, que **coordina** los extractores, **clasifica**, **compone el informe** y **publica** en Teams.

Escanear y publicar son el mismo flujo: la publicación añade los pasos de borrador, confirmación y envío.

Intervienen dos subagentes de solo lectura, `product-forge-incidencias-teams-extractor` y `product-forge-incidencias-jira-extractor`. No comparten memoria: pásales todo el contexto que necesiten, incluida la norma de castellano. El resto de pasos, incluida la clasificación, son tuyos. Los criterios de clasificación están en [clasificacion.md](clasificacion.md).

## Disparadores típicos

- Solo escaneo: "temas pendientes", "hilos pendientes", "incidencias pendientes", "hilos sin responder", "escanea los canales", "ITSMECOM", "qué tenemos en Incidencias".
- Con publicación: "publica el resumen", "envíalo a la daily", "mándamelo al chat".

## Parámetros

- **Rango temporal**: por defecto últimos **7 días** sobre la creación del hilo (post raíz); las respuestas se leen completas aunque sean posteriores. El usuario puede indicar otro rango.
- **Canales**: por defecto los **15** (7 de incidencias del squad/área + 8 de soporte de API Storefront e implantación por cadena; ver procedimiento). El usuario puede acotarlos o excluir los de implantación.
- **Scope de los canales**: `interno` = solo miembros de PACMAN (SQUAD Product Forge 🛠️, Incidencias 🐞, PACMAN Contributors); `externo` = abierto a toda la organización (B - Gestión incidencias Tecnología, P - Dudas técnicas, PRO Validación Pruebas, Incidencias Entornos Previos, Q - Soporte API Storefront e Imp. XXX). El scope **no** determina la relevancia: solo el contexto y el filtro de cada canal.
- **Filtro reforzado (solo Q - Soporte API Storefront e Imp. XXX)**: en esos 8 canales solo entran los hilos que mencionan **Storefront** (o una etiqueta del squad) **y** contienen una **URL de API de Producto** (segmento `/product`, `/products` o `/productsArray` en el path). Las dos condiciones son obligatorias. Los demás canales externos (B, P, PRO Validación Pruebas, Entornos Previos) se filtran solo por mención al squad, como los internos.
- **PRs cerradas**: si incluir hilos con PR cerradas (por defecto no; ver clasificación).
- **Publicar**: por defecto **no**. Solo se publica si el usuario lo pide en la petición o lo solicita tras ver el informe.
- **Destino** (solo si publica):
  - **Por defecto:** chat de grupo `19:c464808cd0a54e2ba8ee742d995f2341@thread.v2` (HTML directo). Es un chat con otras personas: indícalo en la confirmación.
  - **Hilo de la daily** en el canal «SQUAD Product Forge 🛠️», solo si lo pide.
  - **Chat privado del usuario** (`48:notes`), solo si lo pide expresamente.

Comandos, identificadores y cautelas de publicación están en la skill `/product-forge-teams`.

## Procedimiento

1. **Alcance**: resuelve los parámetros anteriores y la **lista de miembros de ProductForge** (de `team.adoc`, según tus reglas comunes).
2. **Obtención en paralelo** (subagentes de solo lectura). **REGLA OBLIGATORIA, no se negocia ni requiere que el usuario la recuerde:** lanza **en un único bloque de llamadas, en primer plano (sin `background`)**, **15 instancias** de `product-forge-incidencias-teams-extractor` (**una por canal**) **más** la de `product-forge-incidencias-jira-extractor`: 16 llamadas simultáneas. **Prohibido** lanzar una sola instancia de Teams para varios canales, lanzarlas en secuencia, usarlas en segundo plano o hacer `sleep`/esperas manuales. Los canales (el detalle de IDs lo conoce el extractor; basta pasarle el nombre y el número) son:
   - **Canales del squad y de incidencias (1–7):** 1 SQUAD Product Forge 🛠️, 2 Incidencias 🐞, 3 PACMAN Contributors, 4 B - Gestión incidencias Tecnología, 5 P - Dudas técnicas, 6 PRO Validación Pruebas, 7 Incidencias Entornos Previos.
   - **Canales de soporte de API e implantación (8–15, todos externos):** 8 Q - Soporte API Storefront, 9 Imp. Bershka, 10 Imp. Lefties, 11 Imp. Massimo Dutti, 12 Imp. Oysho, 13 Imp. Pull and Bear, 14 Imp. Stradivarius, 15 Imp. Zara Home.

   Si el usuario acota canales, una instancia por cada canal pedido; si pide explícitamente excluir los de implantación, no lances los 8–15 (indícalo en el alcance del informe). A cada instancia pásale su canal como subconjunto, el rango, la lista de miembros, el parámetro «PRs cerradas», la norma de castellano y la de horas en Europe/Madrid (datos objetivos de hilos relevantes y sus respuestas). **A las instancias 8–15 pásales además, textualmente, el criterio reforzado del extractor** (mención a Storefront **y** URL con `/product` en el path, ambas obligatorias) y recuérdales que deben devolver `descartadosPorFiltro` y no volcar hilos que solo hablen de otros equipos. A las instancias 4–7 (B, P, PRO Validación Pruebas, Entornos Previos) **no** les pidas ese filtro: son externos pero se filtran solo por mención al squad. Jira: `product-forge-incidencias-jira-extractor` (ITSMECOM abiertos con todos sus comentarios, datos objetivos). Si ya hay datos recientes de esta sesión con el mismo alcance, reutilízalos. Si vas a publicar, pide los **informes previos** de los últimos 7 días (ver «Informes previos») a **una sola** instancia de `teams-extractor`. Une los resultados de todas las instancias sin modificarlos (hilos y bloques de cobertura y limitaciones de cada canal); si una instancia falla, indícalo como limitación del canal.

3. **Clasificación y cotejo (tuyos):** clasifica cada hilo y ticket aplicando [clasificacion.md](clasificacion.md) sobre los datos **íntegros** de los extractores (sin resumir ni recortar). Antes de presentar nada, revisa el conjunto:
   - Coherencia con clasificaciones previas de la sesión para el mismo hilo o ticket.
   - Las limitaciones y la cobertura de los extractores (rango cubierto, canales inaccesibles, miembros no verificados, lecturas fallidas) se muestran al usuario.
4. **Presentación (informe mínimo)**: compón el informe según «Formato del informe» y muéstralo. Ampliar contexto solo si el usuario lo pide (vuelve a delegar el hilo/ticket concreto).
5. **Si no se publica**: termina ofreciendo ampliar contexto o publicar el resumen, sin más texto.
6. **Si se publica** (acción que modifica estado):
   1. Con los informes previos devueltos por `teams-extractor`, aplica las reglas de «Informes previos» y compón el **borrador** según «Mensaje de publicación». Indica al usuario cuántos resueltos se han omitido.
   2. Muestra al usuario el borrador tal y como se verá en Teams y el **destino exacto**, y pide confirmación con `question`. Cada versión nueva requiere una confirmación nueva.
   3. Solo con un "sí" claro, **publica tú** el texto exacto confirmado en el destino (skill `/product-forge-teams`), tras repetir la comprobación previa. No permitas que el texto cambie entre borrador y envío.
   4. Informa del resultado. Recuerda que los mensajes enviados no se pueden editar ni borrar.

## Formato del informe (escaneo)

**Por defecto el informe es mínimo.** El contexto se da solo si el usuario lo pide. No muestres preview largo ni explicaciones no solicitadas.

Cada hilo o ticket lleva **dos emojis**, siempre **los primeros de cada viñeta** y en este orden: 1º criticidad, 2º atendido (significado en [clasificacion.md](clasificacion.md)).

1. Una línea de alcance: canales, rango, zona horaria (`Europe/Madrid`) y nº de hilos relevantes. Indica que Q - Soporte API Storefront y los Imp. XXX se han filtrado por mención a Storefront + URL de API de Producto.
2. Tabla resumen por canal **solo sobre pendientes** (🫥 y 🏃‍♂️‍➡️): nº de pendientes y su desglose por criticidad 🔴 🟠 🟡 ⚪ y por atención 🫥 🏃‍♂️‍➡️, solo con los canales que tengan pendientes. Los recuentos se obtienen contando tu clasificación, no se estiman. Incluye ITSMECOM como una fila más.
3. **Pendientes (🫥 y 🏃‍♂️‍➡️)**, ordenados según «Orden», **una sola línea por elemento**: criticidad + atendido · fecha · antigüedad · canal · autor · tema en pocas palabras · URL completa en texto visible. Marca con «(PR abierta)» los hilos del equipo. Separa hilos de Teams, incidencias ITSMECOM y consultas ITSMECOM.
4. No listes por defecto resueltos (✅), informativos, motivos ni observaciones. Añade una única línea final «Omitidos: N resueltos, N informativos, N PR cerradas» (contados desde tu clasificación) y avisa solo de limitaciones que afecten al resultado (canal inaccesible, miembros no verificados, truncado).

**Orden dentro de cada bloque** (informe y mensaje): primero por criticidad (🔴, 🟠, 🟡, ⚪) y, dentro de la misma, por atendido (🫥, 🏃‍♂️‍➡️, ✅). A igualdad de ambos, del más antiguo al más reciente.

## Mensaje de publicación (borrador y envío)

- **Título**: primera línea tras el aviso de IA obligatorio (skill `/product-forge-teams`): `**Temas pendientes entre dd/mm/aaaa y dd/mm/aaaa**` (inicio y fin del informe), seguida de línea en blanco. Es la única línea que no es viñeta ni cabecera de bloque.
- Mensaje **conciso**, **un tema por línea** como viñeta, con las particularidades de formato de `/product-forge-teams`. Sin línea de «Urgente» ni texto adicional.
- **Cinco bloques**, en este orden, cada uno ordenado según «Orden» y omitido si está vacío: 1º «Hilos abiertos por personas externas» (🫥/🏃‍♂️‍➡️ de Teams); 2º «Incidencias ITSMECOM»; 3º «Consultas ITSMECOM»; 4º «Hilos internos» (hilos del equipo con PR abierta); 5º «Hilos externos resueltos» (✅ iniciados por personas externas). Los bloques 1 a 4 llevan solo pendientes; los ✅ van solo en el 5º.
- **Hilos de Teams**: `- <criticidad> <atendido> [título](webUrl) · dd/mm`. En el 1er bloque el texto del enlace empieza por el nombre completo del canal (`[<Canal>: <título>]`, sin sufijo «Canal …»). En hilos del equipo, el texto es el título de la PR (`gh pr view`), la principal si hay varias.
- **Líneas ITSMECOM**: `- <criticidad> <atendido> [ITSMECOM-N](https://jira.inditex.com/jira/browse/ITSMECOM-N): <título> · dd/mm — <estado>. <descripción>`. El enlace va **solo sobre el ID**; la fecha es la de creación. El estado es «En curso, asignado a <nombre>» o «En cartera, sin asignar». La descripción (ver clasificación) es obligatoria.
- **Resumen de estado**: en TODOS los hilos 🏃‍♂️‍➡️ y ✅ añade tras la fecha ` — <resumen breve>` (ver clasificación). Los 🫥 no llevan resumen.
- **Texto limpio**: cada hilo o ticket aparece una sola vez; sin corchetes (quítalos de títulos y resúmenes) ni textos truncados; mantén una única fuente del texto.
- **Comprobación previa al envío**: valida con regex que cada línea de viñeta cumple el formato anterior, por ejemplo `^- (🔴|🟠|🟡|⚪) (🏃‍♂️‍➡️|🫥|✅) \[[^\[\]]+\]\(https://[^)\s]+\)(: [^\[\]]+?)? · \d\d/\d\d( — [^\[\]]+)?$`, y no envíes si alguna falla.
- Avisa de que los mensajes enviados no se pueden editar ni borrar.

### Informes previos

Con los informes `Temas pendientes entre …` de los últimos 7 días que devuelve `teams-extractor`, **omite del 5º bloque los ✅ que ya aparezcan como resueltos** en alguno (identifícalos por `webUrl`/clave). Los hilos todavía abiertos (🫥/🏃‍♂️‍➡️, incluidos ITSMECOM) **se incluyen siempre**, y un hilo que antes estaba pendiente y ahora está resuelto se incluye como resuelto. Si el 5º bloque queda vacío, omítelo. Informa al usuario de cuántos se han omitido y de qué mensaje(s), o de que no había informe previo. Si `teams` no pudo leer el hilo, indícalo como limitación y no omitas nada.

## Reglas

Aplican además tus reglas comunes (castellano, horas en `Europe/Madrid`, no inventar, mostrar limitaciones, confirmación explícita).

- Pasa a los extractores la norma de castellano y la de horas.
- Los extractores son de solo lectura; clasificar y publicar lo haces tú, y publicar solo con confirmación explícita.
