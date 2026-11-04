---
name: product-forge-incidencias
description: Flujo de temas pendientes del squad Products Forge.
---

# Product Forge: incidencias pendientes (Teams + Jira)

> **Invocación explícita obligatoria:** esta skill solo se ejecuta cuando el usuario la pide de forma explícita. No la cargues ni ejecutes por inferencia, por coincidencia con la descripción ni desde otra skill o subagente. Si dudas de que la petición sea explícita, pregunta antes con la herramienta `question`.

Flujo para obtener los temas pendientes del squad Products (Product Forge): hilos de Teams que mencionan al squad —incluidos los canales de soporte de API Storefront y de implantación por cadena, filtrados por mención a Storefront y URL de API de Producto— y tickets ITSMECOM abiertos. Opcionalmente, publica el resumen en Teams. Lo ejecuta el agente principal `product-forge-pana`, que **coordina** los extractores, **clasifica**, **compone el informe** y **publica** en Teams.

Escanear y publicar son el mismo flujo: la publicación añade los pasos de borrador, confirmación y envío.

Intervienen dos subagentes de solo lectura, `product-forge-incidencias-teams-extractor` y `product-forge-incidencias-jira-extractor`. No comparten memoria: pásales todo el contexto que necesiten, incluida la norma de castellano. **Por defecto solo se lanza el de Jira**: la lectura de los 15 canales la hace el barrido único descrito en el paso 2. El resto de pasos, incluida la clasificación, son tuyos. Los criterios de clasificación están en [clasificacion.md](clasificacion.md).

La lectura de los canales la hace el script `scripts/barrido.py`, que recorre todos los canales del alcance en una sola invocación y se apoya en `scripts/extract_channel.py` (pagina las respuestas completas, corta por fecha y aplica los filtros de mención y de URL de Producto). El barrido es la vía normal; los subagentes ya no leen canales salvo para un hilo concreto. Nadie debe montar su propio extractor con `jq` y `xargs`, ni reejecutar el script con otros flags para «verificar».

## Disparadores típicos

- Solo escaneo: "temas pendientes", "hilos pendientes", "incidencias pendientes", "hilos sin responder", "escanea los canales", "ITSMECOM", "qué tenemos en Incidencias".
- Con publicación: "publica el resumen", "envíalo a la daily", "mándamelo al chat".

## Parámetros

- **Rango temporal**: por defecto últimos **7 días** sobre la creación del hilo (post raíz); las respuestas se leen completas aunque sean posteriores. El usuario puede indicar otro rango.
- **Canales**: por defecto los **15**, todos equivalentes: 7 de incidencias del squad/área (1–7) y 8 externos (8 Q - Soporte API Storefront y 9–15 Imp. por cadena). Los lee el barrido único (ver «Lectura de Teams»). El usuario puede acotarlos o excluir los de implantación.
- **Scope de los canales**: `interno` = solo miembros de PACMAN (SQUAD Product Forge 🛠️, Incidencias 🐞, PACMAN Contributors); `externo` = abierto a toda la organización (B - Gestión incidencias Tecnología, P - Dudas técnicas, PRO Validación Pruebas, Incidencias Entornos Previos, Q - Soporte API Storefront e Imp. XXX). El scope **no** determina la relevancia: solo el contexto y el filtro de cada canal.
- **Filtro reforzado (solo Q - Soporte API Storefront e Imp. XXX)**: en esos 8 canales solo entran los hilos que mencionan **Storefront** (o una etiqueta del squad) **y** contienen una **URL de API de Producto** (segmento `/product`, `/products` o `/productsArray` en el path). Las dos condiciones son obligatorias. Los demás canales externos (B, P, PRO Validación Pruebas, Entornos Previos) se filtran solo por mención al squad, como los internos.
- **PRs cerradas**: si incluir hilos con PR cerradas (por defecto no; ver clasificación).
- **Publicar**: por defecto **no**. Solo se publica si el usuario lo pide en la petición o lo solicita tras ver el informe.
- **Destino** (solo si publica):
  - **Por defecto:** chat de grupo `19:c464808cd0a54e2ba8ee742d995f2341@thread.v2` (HTML directo). Es un chat con otras personas: indícalo en la confirmación.
  - **Hilo de la daily** en el canal «SQUAD Product Forge 🛠️», solo si lo pide.
  - **Chat privado del usuario** (`48:notes`), solo si lo pide expresamente.

Comandos, identificadores y cautelas de publicación están en la skill `/product-forge-teams`.

## Lectura de Teams

Esta sección es la **fuente única** de cómo se leen los canales. Ni el subagente ni ninguna otra skill deben repetirla.

### Barrido único (vía normal)

```bash
python3 .opencode/skills/product-forge-incidencias/scripts/barrido.py \
  "<desde_iso>" "<dir_salida>" [--desde-ultima-actividad] [--canales 1,2,4] [--workers-canal 5]
```

Recorre todos los canales en paralelo dentro de una sola invocación y deja `canal_NN.json` por canal. **Medido: 15 canales en ~80 s** (con 15 subagentes el mismo trabajo tardaba ~25 min). `--desde-ultima-actividad` es obligatorio para el alcance completo: incluye hilos abiertos antes del rango que siguen vivos.

### Canales y filtros

| # | Canal | Scope | Team | Channel ID | Filtro aplicado por el barrido |
|---|-------|-------|------|------------|-------------------------------|
| 1 | SQUAD Product Forge 🛠️ | interno | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:c2d93e0c05834c5f885f7ebbb2a82da8@thread.tacv2` | sin filtro de mención (excepción) |
| 2 | Incidencias 🐞 | interno | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:d311bbd5ba844456a3f88ca0f8fcc1ec@thread.tacv2` | sin filtro: el canal implica al squad |
| 3 | PACMAN Contributors | interno | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:TFiV3Qv4kALmUMHeZJxzjdivoSYvaQ64PtQ0hPlG0tM1@thread.tacv2` | sin filtro: el canal implica al squad |
| 4 | B - Gestión incidencias Tecnología | externo | `fc58da2f-67b0-49ab-a3df-d2b84d676f26` | `19:38382f0598414c04b7a4354ea823f795@thread.tacv2` | mención al squad |
| 5 | P - Dudas técnicas | externo | `fc58da2f-67b0-49ab-a3df-d2b84d676f26` | `19:d63e20f255304e7ea5c97cd0a6ba760c@thread.tacv2` | mención al squad |
| 6 | PRO Validación Pruebas | externo | `2f537452-376a-4f33-9599-064664d6bdd9` | `19:c3089f466c1d4bdc92182b223200430a@thread.skype` | mención al squad |
| 7 | Incidencias Entornos Previos | externo | `f74cb4b3-da66-493b-9d82-73c24b3cdfc7` | `19:d89dd36e316e46579af64fabe29a63a4@thread.tacv2` | mención al squad |
| 8 | Q - Soporte API Storefront | externo | `fc58da2f-67b0-49ab-a3df-d2b84d676f26` | `19:da2d4f13877c45639e78b833a4140a45@thread.tacv2` | Storefront + URL de Producto |
| 9 | Imp. Bershka | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:4OYdxDq5c2-ke6zi6Yv-GbI6lTOCls0NHQeDZuWmddg1@thread.tacv2` | Storefront + URL de Producto |
| 10 | Imp. Lefties | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:gxYlnS2grspTncMANce2vqY_c9ixe_nHqlLwrRyRGrk1@thread.tacv2` | Storefront + URL de Producto |
| 11 | Imp. Massimo Dutti | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:XH0mKWw2z0beuHP819Yt6YCY9myrNTu3Jr-ZBUlfIqQ1@thread.tacv2` | Storefront + URL de Producto |
| 12 | Imp. Oysho | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:uQnRglYGNy-yYOzMaEFgy5EP9jO8I9z7Z4QSHNKLBTE1@thread.tacv2` | Storefront + URL de Producto |
| 13 | Imp. Pull and Bear | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:tCR1SuX9xZZEImROkyJ5n4AxUX1fSprq3-55DLtazQI1@thread.tacv2` | Storefront + URL de Producto |
| 14 | Imp. Stradivarius | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:mF1UCTeEURR_4mSSlGqMq58IJ_XOaLJqLkEem7e6Mas1@thread.tacv2` | Storefront + URL de Producto |
| 15 | Imp. Zara Home | externo | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:7_n40ZpehZYr-aOqZZ8W1PTa10wZ-o5JCjk6QFpFEr81@thread.tacv2` | Storefront + URL de Producto |

- **Mención al squad (4–7):** etiqueta o texto `ProductForge`, `Store Front Producto`, `ComercialProducto`, `ComercialProductoStore`, `Pacman Contributors`, `Pacman Products`, o mención a un **miembro** del squad (`mentions[].mentionText`). Los nombres de personas se buscan solo en `mentions`, para no confundir una respuesta escrita por un miembro con una mención a ese miembro.
- **Filtro reforzado (8–15), dos condiciones obligatorias** sobre el hilo completo (raíz o respuestas): (1) mención a **Storefront** o a una etiqueta del squad en el **texto o las etiquetas**, no vale solo dentro de la URL; (2) al menos una **URL de API de Producto**, con `/product`, `/products` o `/productsArray` como segmento del path. No cuentan `/stores/{id}/menu`, `/tags`, `/grids`, `/checkout` ni pantallas del frontal de Pacman. Las URLs se extraen de los `href`, porque Teams trunca el texto visible con «…»; si la única evidencia está en una imagen adjunta, no cuenta.

Cada hilo del JSON sale con `menciones_squad`, y cada respuesta con sus `menciones`, `texto` y `fecha` en `Europe/Madrid`.

### Qué hace el script y qué no hay que repetir

`extract_channel.py` pagina las respuestas completas (el CLI corta en 50), corta por fecha, trae las respuestas incrustadas en la página de raíces (`$expand=replies`) y detecta los hilos antiguos con actividad. Por eso:

- **No reejecutes el script por canal ni lo verifiques con el CLI.** Relanzarlo con `--sin-filtro`, con otros `--workers` o barriendo respuestas a mano con `xargs` duplica el tiempo sin cambiar el resultado.
- **No montes extractores propios con `jq`/`xargs`.**
- Si un hilo concreto necesita más contexto, se lee ese hilo (`channel replies`), no el canal entero.

### Respaldo: CLI de Teams

Solo si el script falla (Graph no disponible, cambio de contrato del paquete compartido). En ese caso, y solo entonces: lista los raíces y filtra por fecha en local, lee las respuestas de todos los hilos del rango con concurrencia acotada a **8 procesos** (`xargs -P 8`), procesa los JSON en una sola pasada y **relanza solo** los que tengan `.err` no vacío, con `-P 2`. Un `.err` no vacío significa «respuestas no leídas», nunca «sin respuestas». Aplica el criterio de parada de `/product-forge-teams` (raíces consecutivos anteriores al inicio del rango, ignorando outliers) e itera `--pages 4`, `8`… sin ampliar páginas «por verificar». Si se usa esta vía, hay que decirlo en el bloque de limitaciones: puede haber hilos truncados a 50 respuestas.

## Procedimiento

1. **Alcance**: resuelve los parámetros anteriores y la **lista de miembros de ProductForge** (de `team.adoc`, según tus reglas comunes).
2. **Obtención en un único barrido** (solo lectura). El trabajo de red lo hace **un proceso**, no 15 subagentes: lanza **tú** `scripts/barrido.py`, que recorre todos los canales del alcance en paralelo dentro de una sola invocación y deja un JSON por canal. El procedimiento y los detalles de lectura están en **«Lectura de Teams»**, más abajo:

   ```bash
   python3 .opencode/skills/product-forge-incidencias/scripts/barrido.py \
     "<desde_iso>" "<dir_salida>" [--desde-ultima-actividad] [--canales 1,2,4] [--workers-canal 5]
   ```

   Lee tú los JSON del directorio de salida y clasifica con ellos. Si un canal sale con `error`, indícalo como limitación del canal. Si el usuario acota canales, pásalos en `--canales`; si pide excluir los de implantación, no incluyas los 9–15 e indícalo en el alcance del informe. Si ya hay datos recientes de esta sesión con el mismo alcance, reutilízalos.

   **Subagentes: solo Jira por defecto.** Lanza `product-forge-incidencias-jira-extractor` (ITSMECOM abiertos con todos sus comentarios) siempre. El `teams-extractor` **solo** hace falta para algo que el barrido no da: los **informes previos** de los últimos 7 días cuando se va a publicar, o una duda material sobre un hilo concreto (pásale el `rootId` y dile que **no relea el canal**).

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
