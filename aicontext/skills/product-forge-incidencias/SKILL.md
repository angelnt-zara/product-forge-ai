---
name: product-forge-incidencias
description: Flujo de temas pendientes del squad Products Forge.
---

# Product Forge: incidencias pendientes (Teams + Jira)

> **Invocación explícita obligatoria:** esta skill solo se ejecuta cuando el usuario la pide de forma explícita. No la cargues ni ejecutes por inferencia, por coincidencia con la descripción ni desde otra skill o subagente. Si dudas de que la petición sea explícita, pregunta antes con la herramienta `question`.

Flujo para obtener los temas pendientes del squad Products (Product Forge): hilos de Teams que mencionan al squad —incluidos los canales de soporte de API Storefront y de implantación por cadena, filtrados por mención a Storefront y URL de API de Producto— y tickets ITSMECOM abiertos. Opcionalmente, publica el resumen en Teams. Lo ejecuta el agente principal `product-forge-pana`, que **coordina** los extractores, **clasifica**, **compone el informe** y **publica** en Teams.

Escanear y publicar son el mismo flujo: la publicación añade los pasos de borrador, confirmación y envío.

Interviene un único subagente de solo lectura, `product-forge-incidencias-teams-extractor`, y solo para lo que el barrido no da (informes previos antes de publicar o una duda material sobre un hilo concreto). **No hay subagente de Jira**: los ITSMECOM abiertos los obtiene el agente principal en línea con el MCP (ver paso 2), porque delegarlos costaba una sesión de modelo completa para dos llamadas que tardan ~2 s. Los subagentes no comparten memoria: pásale todo el contexto que necesite, incluida la norma de castellano. El resto de pasos, incluida la clasificación, son tuyos. Los criterios de clasificación están en [clasificacion.md](clasificacion.md).

La lectura de los canales la hace el script `scripts/barrido.py`, que recorre todos los canales del alcance en una sola invocación y se apoya en `scripts/extract_channel.py` (pagina las respuestas completas, corta por fecha y aplica los filtros de mención y de URL de Producto). El barrido es la vía normal; los subagentes ya no leen canales salvo para un hilo concreto. Nadie debe montar su propio extractor con `jq` y `xargs`, ni reejecutar el script con otros flags para «verificar».

Tres scripts más completan el flujo, y cada uno existe por un motivo medido:

| Script | Para qué | Por qué existe |
|---|---|---|
| `scripts/detalle.py` | texto íntegro de los hilos candidatos | evita releer los JSON completos; recorta los hilos largos |
| `scripts/prs.py` | estado de las PR enlazadas, en lote | sin él la regla «PR aprobada ⇒ resuelto» no se aplicaba nunca |
| `scripts/itsmecom.py` | ITSMECOM citados por hilo + JQL de verificación | sin él los hilos cuyo caso se cerró en Jira seguían publicándose como pendientes |

## Disparadores típicos

- Solo escaneo: "temas pendientes", "hilos pendientes", "incidencias pendientes", "hilos sin responder", "escanea los canales", "ITSMECOM", "qué tenemos en Incidencias".
- Con publicación: "publica el resumen", "envíalo a la daily", "mándamelo al chat".

## Parámetros

- **Rango temporal**: por defecto últimos **7 días** sobre la creación del hilo (post raíz); las respuestas se leen completas aunque sean posteriores. El usuario puede indicar otro rango.
- **Canales**: por defecto los **16**, todos equivalentes: 7 de incidencias del squad/área (1–7) y 9 externos con filtro reforzado (8 Q - Soporte API Storefront, 9–15 Imp. por cadena y 16 Storefront API, canal sobre todo de anuncios). Los lee el barrido único (ver «Lectura de Teams»). El usuario puede acotarlos o excluir los de implantación.
- **Scope de los canales**: `interno` = solo miembros de PACMAN (SQUAD Product Forge 🛠️, Incidencias 🐞, PACMAN Contributors); `externo` = abierto a toda la organización (B - Gestión incidencias Tecnología, P - Dudas técnicas, PRO Validación Pruebas, Incidencias Entornos Previos, Q - Soporte API Storefront e Imp. XXX). El scope **no** determina la relevancia: solo el contexto y el filtro de cada canal.
- **Filtro reforzado (solo Q - Soporte API Storefront, Imp. XXX y Storefront API)**: en esos 9 canales solo entran los hilos que mencionan **Storefront** (o una etiqueta del squad) **y** contienen una **URL de API de Producto** (segmento `/product`, `/products` o `/productsArray` en el path). Las dos condiciones son obligatorias. **Además se comprueba a quién se dirige el hilo** (`destinatario_canales_externos`): «Storefront» es también el nombre de la familia de APIs que consumen Grids y Navigation y forma parte del nombre de otro equipo («Storefront Parrillas»), así que un hilo dirigido a otro squad de PACMAN se omite aunque pase el filtro. Los demás canales externos (B, P, PRO Validación Pruebas, Entornos Previos) se filtran solo por mención al squad, como los internos.
- **Relevancia estricta en Incidencias 🐞 (canal 2)**: el barrido **no** aplica filtro en este canal, pero al clasificar solo se incluye un hilo si **menciona explícitamente al squad o a un miembro de ProductForge** (lista de `team.adoc`, más Elias Ferreiro Borreiros), en el raíz o en cualquier respuesta. La única excepción es un hilo abierto por **alguien de fuera** en el que un miembro del squad entra a responder. **Que el raíz lo escriba un miembro del squad no basta**: si además solo menciona a otros squads, es una reclamación a otro equipo y se omite como ✅ (el extractor lo marca con `reclama_a_otro`). Si no se cumple nada de lo anterior, el hilo se omite como ajeno, citando el squad propietario cuando se pueda identificar en `team.adoc`, y se cuenta en la línea de «Omitidos». Detalle en `clasificacion.md`.
- **Hilo sin respuestas: prohibido clasificar por el título.** Hay que leer el cuerpo del raíz (`texto_raiz`, visible en el índice y en la línea `RAÍZ:` de `detalle.py`). Si no está disponible, el hilo se marca «no verificable» en limitaciones, nunca 🫥 por defecto.
- **Dudas razonables: pregunta con enlace.** Si la clasificación de un hilo o ticket no es concluyente, no decidas en solitario: pregunta al usuario con `question`, incluyendo siempre el **enlace completo visible** (`webUrl` o URL del ticket) para que pueda verificarlo en un clic. **El enlace va siempre solo en una línea nueva, al final del enunciado y sin texto detrás** (si va al final de una línea de texto, la consola lo parte y no se abre). Si hay varias dudas, van en la misma llamada. Detalle en `clasificacion.md`.
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
  "<desde_iso>" "<dir_salida>" [--canales 1,2,4] [--workers-canal 16]
```

Recorre todos los canales en paralelo dentro de una sola invocación y deja `canal_NN.json` por canal **y `indice.txt`**. **Medido: 15 canales en ~17-20 s (ahora 16, sin remedir)** (antes 93 s; con 15 subagentes el mismo trabajo tardaba ~25 min). Los hilos abiertos antes del rango que siguen vivos se incluyen **por defecto** (`--sin-ultima-actividad` lo desactiva).

**De dónde salió la mejora (no la deshagas).** El barrido pedía siempre 8 páginas por canal. Medido con `PF_TEAMS_VERBOSE_PAGINAS=1`: de las 8 páginas del canal 2 solo la primera tenía mensajes en rango, y las 7 restantes costaban 42 de los 52 s del canal (paginación profunda de Graph, hasta 16 s por página) sin devolver ni un mensaje útil. Ahora se para tras 2 páginas consecutivas sin nada en rango cuya página más antigua ya quede fuera del rango. Verificado contra el barrido completo: **0 hilos perdidos y `indice.txt` idéntico byte a byte**. No bajes esa ventana a 1 página: el orden de raíces no es estrictamente cronológico (la primera página del canal 1 mezcla 2025-07 con 2026-11). `$filter` por fecha y `$top=200` devuelven 400 en Graph beta.

### Lectura en una sola pasada (obligatorio)

El JSON por canal son ~430 KB y **el 83 % de su texto se descarta al clasificar** (medido en el informe del 18/10–04/11: 130.529 de 157.594 caracteres). No abras los `canal_NN.json` para clasificar. El flujo es:

1. **Lee `indice.txt`** (~28 KB, una línea por hilo): `id | fecha | autor | respuestas y respuestas del squad | última actividad y si el último es del squad | urls de Producto y marcas de relevancia | título | último mensaje o, si no hay respuestas, el texto del raíz (300 caracteres)`.
2. **Decide los candidatos** con esa línea: un hilo con `squad=0` o cuyo `ult` no sea del squad (`-`) es candidato a 🫥; si el último mensaje es del squad (`S`), probablemente esté resuelto. Las marcas `[raizAUTOR, otro=Grids, RECLAMA_A_OTRO]` indican que el hilo lo abrió un miembro del squad para reclamar a otro equipo: esos se omiten como ✅, no son pendientes.
3. **Pide el texto íntegro de TODOS los candidatos en UNA sola invocación**, sin volver a llamar a Teams:

```bash
python3 .opencode/skills/product-forge-incidencias/scripts/detalle.py "<dir_salida>" <id> [<id> ...]
# opciones: --canal N · --max-resp N (solo las N más recientes) · --chars N · --listar · --completas
```

**Una sola llamada, no cuatro.** Decide todos los candidatos con el índice y pásalos de golpe; en el informe del 18/10–04/11 se hicieron 4 tandas (14 KB + 88 KB + 7 KB + 16 KB) porque se iban descubriendo sobre la marcha, y eso son 3 vueltas de modelo de más para el mismo dato. Los ids se aceptan separados por espacios, comas o dentro de un argumento entrecomillado: antes, un argumento con varios ids se tomaba como un id único, no se encontraba y el comando salía con **0 bytes**, indistinguible de «no hay nada que leer» y con riesgo de clasificar a ciegas.

**Hilos largos: recorte automático.** Por encima de **20 respuestas** `detalle.py` muestra solo las **12 más recientes** y avisa por pantalla. Medido: 5 hilos concentraban 130 KB de los 430 KB del JSON, y los 3 que se abrieron completos (67 KB) se resolvían igual con las 12 últimas respuestas (**8,7 KB, −87 %**). El estado de un hilo lo decide su cola, no su cabecera. Usa `--completas` (o `--max-resp N`) solo cuando el arranque del hilo sea material.

El índice da la señal de triage; `detalle.py` da el texto completo de lo que de verdad hay que clasificar. **No generes un `digest.txt` intermedio ni vuelvas a leer los JSON completos**: eso es releer tres veces el mismo dato y es lo que hacía tardar el informe.

Si un hilo necesita más contexto del que da el índice, se pide con `detalle.py`, no releyendo el canal.

### Canales y filtros

| # | Canal | Scope | Team | Channel ID | Filtro aplicado por el barrido |
|---|-------|-------|------|------------|-------------------------------|
| 1 | SQUAD Product Forge 🛠️ | interno | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:c2d93e0c05834c5f885f7ebbb2a82da8@thread.tacv2` | sin filtro de mención (excepción) |
| 2 | Incidencias 🐞 | interno | `1301738f-827e-48ec-8770-3f0922c1c295` | `19:d311bbd5ba844456a3f88ca0f8fcc1ec@thread.tacv2` | **mención estricta**: al squad o a un miembro, o participación de un miembro |
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
| 16 | Storefront API (canal de anuncios) | externo | `84b73c44-5251-4874-ab8b-c38f48ea64f4` | `19:94d12a174f634914a552731714e61cac@thread.tacv2` | Storefront + URL de Producto |

- **Mención al squad (4–7):** etiqueta o texto `ProductForge`, `Store Front Producto`, `ComercialProducto`, `ComercialProductoStore`, `Pacman Contributors`, `Pacman Products`, o mención a un **miembro** del squad (`mentions[].mentionText`). Los nombres de personas se buscan solo en `mentions`, para no confundir una respuesta escrita por un miembro con una mención a ese miembro.
- **Filtro reforzado (8–16), dos condiciones obligatorias** sobre el hilo completo (raíz o respuestas): (1) mención a **Storefront** o a una etiqueta del squad en el **texto o las etiquetas**, no vale solo dentro de la URL; (2) al menos una **URL de API de Producto**, con `/product`, `/products` o `/productsArray` como segmento del path. No cuentan `/stores/{id}/menu`, `/tags`, `/grids`, `/checkout` ni pantallas del frontal de Pacman. Las URLs se extraen de los `href`, porque Teams trunca el texto visible con «…»; si la única evidencia está en una imagen adjunta, no cuenta.
- **Destinatario (8–16), tercera comprobación**: que el hilo mencione «Storefront» no implica que sea nuestro, porque esa palabra es el nombre genérico de la familia de APIs que también consumen Grids y Navigation y forma parte del nombre de otro equipo («Storefront Parrillas»). El extractor decide en tres estados —`mantener` si hay mención al squad o participación de un miembro, `excluir` si el raíz se dirige a otro squad de PACMAN, `preguntar` si no hay señal— y los `preguntar` llegan en `excluidos` con `dudoso: true` para consultarlos al usuario con el enlace. Detalle e impacto medido en [clasificacion.md](clasificacion.md), «Destinatario del hilo en los canales 8-16».

Cada hilo del JSON sale con `menciones_squad`, y cada respuesta con sus `menciones`, `texto` y `fecha` en `Europe/Madrid`.

### Qué hace el script y qué no hay que repetir

`extract_channel.py` pagina las respuestas completas (el CLI corta en 50), corta por fecha, trae las respuestas incrustadas en la página de raíces (`$expand=replies`) y detecta los hilos antiguos con actividad. Por eso:

- **No reejecutes el script por canal ni lo verifiques con el CLI.** Relanzarlo con `--sin-filtro`, con otros `--workers` o barriendo respuestas a mano con `xargs` duplica el tiempo sin cambiar el resultado.
- **No montes extractores propios con `jq`/`xargs`.**
- **No reescribas el índice con un script propio ni vuelques los JSON a un fichero intermedio.** `barrido.py` ya deja `indice.txt` y `detalle.py` ya saca el texto íntegro de un id.
- Si un hilo concreto necesita más contexto, se lee ese hilo con `detalle.py <dir> <id>`, no el canal entero.

### Respaldo: CLI de Teams

Solo si el script falla (Graph no disponible, cambio de contrato del paquete compartido). En ese caso, y solo entonces: lista los raíces y filtra por fecha en local, lee las respuestas de todos los hilos del rango con concurrencia acotada a **8 procesos** (`xargs -P 8`), procesa los JSON en una sola pasada y **relanza solo** los que tengan `.err` no vacío, con `-P 2`. Un `.err` no vacío significa «respuestas no leídas», nunca «sin respuestas». Aplica el criterio de parada de `/product-forge-teams` (raíces consecutivos anteriores al inicio del rango, ignorando outliers) e itera `--pages 4`, `8`… sin ampliar páginas «por verificar». Si se usa esta vía, hay que decirlo en el bloque de limitaciones: puede haber hilos truncados a 50 respuestas.

## Procedimiento

1. **Alcance**: resuelve los parámetros anteriores y la **lista de miembros de ProductForge** (de `team.adoc`, según tus reglas comunes).
2. **Obtención en un único barrido** (solo lectura). El trabajo de red lo hace **un proceso**, no 15 subagentes: lanza **tú** `scripts/barrido.py`, que recorre todos los canales del alcance en paralelo dentro de una sola invocación y deja un JSON por canal **y el `indice.txt`**. El procedimiento y los detalles de lectura están en **«Lectura de Teams»**, más arriba:

   ```bash
   python3 .opencode/skills/product-forge-incidencias/scripts/barrido.py \
     "<desde_iso>" "<dir_salida>" [--canales 1,2,4] [--workers-canal 16]
   ```

   Los hilos antiguos con actividad en el rango se buscan **por defecto** (no hay que pasar nada); `--sin-ultima-actividad` lo desactiva. Medido: 15 canales en **~17-20 s** con `--workers-canal 16` (antes 93 s).

   Si un canal sale con `error`, indícalo como limitación del canal. Si el usuario acota canales, pásalos en `--canales`; si pide excluir los de implantación, no incluyas los 9–15 e indícalo en el alcance del informe. Si ya hay datos recientes de esta sesión con el mismo alcance, reutilízalos.

   **Hilos excluidos por relevancia.** Cada `canal_NN.json` trae ahora un array `excluidos` con los hilos que no pasaron el filtro de mención (canal 2), el reforzado (canales 8-16) o la comprobación de destinatario, cada uno con `motivo`, `webUrl`, `texto_raiz`, `autor_raiz_es_squad` y `menciones_otras`. Léelo al clasificar: los de motivo `causa fuera de Pacman, reclamada por el squad` y `destinatario ajeno: …` se cuentan como omitidos; los de `sin mención ni participación del squad` cuyo asunto parezca de Producto/Storefront se **preguntan al usuario** con el enlace, y los marcados `dudoso: true` (motivo `dudoso: sin mención ni destinatario claro`) **siempre** se preguntan, nunca se omiten en silencio (ver `clasificacion.md`, «Hilos excluidos por relevancia» y «Destinatario del hilo en los canales 8-16»).

   **Jira: en línea, sin subagente.** Obtén los ITSMECOM abiertos **tú**, con el MCP de Jira, en paralelo con el barrido. La delegación al subagente `product-forge-incidencias-jira-extractor` se retiró porque costaba una sesión de modelo completa (minutos) para un trabajo que son dos llamadas. Procedimiento:
   1. **Búsqueda: UNA sola llamada con los dos tipos**, no una por tipo. Medido sobre el mismo alcance: dos búsquedas en paralelo tardan **909 ms** y una combinada **384 ms**, con idéntica cobertura (los mismos 8 tickets):
      - `project = ITSMECOM AND status not in (Resolved, Cerrado, Cancelado) AND labels = C-PacmanProduct AND "Equipo Asignado" in (jsdsoportepacman) AND (created >= <desde> OR updated >= <desde>) AND issuetype in (Incidente, "Solicitud de servicio") ORDER BY created ASC`
      Comprueba `total` y pagina con `start_at` hasta cubrirlo: devuelve 10 por página. El tipo de cada ticket viene en `issuetype`, así que se separan incidentes y consultas al clasificar, sin volver a consultar.
   2. **Comentarios**: `jira_get_issue_comments` con `max_results: 3` de todos los tickets **en paralelo** (`Promise.allSettled`). No pidas el histórico completo: el resto se consulta después solo del ticket que lo necesite. Ojo: `jira_search` y `jira_get_issue` no traen comentarios; hay que pedirlos aparte. No bajes de 3: medido, bajar a 2 ahorra un 29 % pero en ITSMECOM-5850604 el comentario que decide el diagnóstico era el 4º.
   3. Anota el campo `assignee` de la búsqueda: distingue «En curso, asignado a <nombre>» de «En cartera, sin asignar» en el informe.

   **PR enlazadas: estado en lote, obligatorio.** Antes de clasificar, resuelve el estado de las PR que los hilos enlazan. Sin esto la regla «hilo de externo con todas las PR aprobadas ⇒ ✅» y «hilo interno con todas las PR cerradas ⇒ omitir» **no se aplicaba nunca**, y en el informe del 18/10–04/11 se publicó como 🟠 🫥 un hilo cuya única petición era aprobar una PR que ya estaba `MERGED` y `APPROVED` (`app-ecommhub#1108`).

   ```bash
   python3 .opencode/skills/product-forge-incidencias/scripts/prs.py "<dir_salida>" [--json] [--hilos <id> ...]
   ```

   - Lee los JSON del barrido (no llama a Teams ni a Jira) y resuelve todas las PR en **una llamada GraphQL en lote** (~1,7 s para 40 PRs, frente a un proceso `gh pr view` por PR). Cada hilo trae ya su campo `prs`, extraído de los `href`.
   - Si una PR no existe o su repo no es accesible, GraphQL falla el lote entero; el script lo **parte en dos y reintenta**, así una PR borrada cuesta unos reintentos y no pierde el estado de las demás.
   - Una PR que no se pudo resolver sale como `DESCONOCIDO`: **no apliques la regla de PR cerrada/aprobada** sobre ella y decláralo en limitaciones.

   El `teams-extractor` **solo** hace falta para algo que el barrido no da: los **informes previos** de los últimos 7 días cuando se va a publicar, o una duda material sobre un hilo concreto (pásale el `rootId` y dile que **no relea el canal**).

   **ITSMECOM citados en los hilos: verificación en lote, obligatoria.** Un hilo puede quedarse sin feedback aunque su caso se haya cerrado en Jira, y un ticket puede haberse reasignado fuera de Pacman. Antes de clasificar, resuelve el estado de los ITSMECOM que citan los hilos y **omite los que estén cerrados o ya no estén asignados al squad**:

   ```bash
   python3 .opencode/skills/product-forge-incidencias/scripts/itsmecom.py "<dir_salida>"
   ```

   - Extrae las claves del título y de todas las respuestas de cada hilo (no llama a Teams) y emite una JQL `key in (...)` lista para pegar, troceada cada 40 claves.
   - Con esas claves, **una sola llamada** a `jira_search` con los campos `summary,status,customfield_18260` (`Equipo Asignado`), más los comentarios de los tickets que queden vivos. Marca los hilos cuyo único ITSMECOM viene en un resumen del bot (varios tickets en un mensaje de reunión): esos no son hilos de incidencia.
   - **La decisión se toma SOLO por estado y `Equipo Asignado`.** Las etiquetas (`C-PacmanProduct`, `C-StoreFront`, `ASIGNACION_INCORRECTA`…) **no se usan**, ni a favor ni en contra. Regla completa en [clasificacion.md](clasificacion.md).
   - La cola válida es `jsdsoportepacman` («N2 Pacman»), la misma que filtra la consulta principal. Otros equipos —incluido `jsddesarrollopacmanproduct` («N3 Pacman»), que es desarrollo, no soporte— cuentan como fuera de Pacman y el hilo se omite citando el equipo real.
   - Ojo: la cola `Equipo Asignado = jsdsoportepacman` es **compartida por todos los squads del área**. Esta verificación es solo para los tickets **citados en hilos**; la consulta principal de abiertos mantiene su filtro, porque sin él la misma ventana pasa de 8 a 62 tickets de Imagen, Assets, Grids, Menú y Tags.

3. **Clasificación y cotejo (tuyos), en una sola pasada de lectura:**
   1. Lee **`indice.txt`** (~28 KB) y haz el triage de los hilos con esa línea.
   2. Pide el texto íntegro de **todos** los candidatos en **una sola invocación** de `detalle.py` (ver «Lectura en una sola pasada»). No abras los `canal_NN.json` para clasificar ni generes ficheros intermedios.
   3. Clasifica cada hilo y ticket aplicando [clasificacion.md](clasificacion.md) sobre los datos **íntegros** de los candidatos (sin resumir ni recortar), y aplica las reglas de PR con el estado que devolvió `prs.py` y las de ITSMECOM con el estado y el equipo que devolvió Jira.
   4. **Puerta de dudas (obligatoria, bloqueante):** aplica el «Control de dudas obligatorio» de [clasificacion.md](clasificacion.md) a todos los elementos y pregunta al usuario con **una sola** `question` por todos los dudosos. No pases al informe ni a ningún borrador hasta tener las respuestas; si no hay dudas, indícalo en el alcance («Sin dudas de clasificación»).
   5. Antes de presentar nada, revisa el conjunto:
      - Coherencia con clasificaciones previas de la sesión para el mismo hilo o ticket.
      - Que todo hilo que cita un ITSMECOM se ha cruzado contra Jira por estado y equipo, sin decidir por etiquetas.
      - Que los hilos cuya causa se ha ubicado fuera de Pacman/Storefront y **no tienen ninguna petición viva hacia el squad** están marcados ✅ y no como pendientes, y que los que sí reclaman algo a Pacman/Storefront siguen pendientes.
      - Las limitaciones y la cobertura de los extractores (rango cubierto, canales inaccesibles, miembros no verificados, lecturas fallidas) se muestran al usuario.
4. **Presentación (informe mínimo)**: compón el informe según «Formato del informe» y muéstralo. Ampliar contexto solo si el usuario lo pide (vuelve a delegar el hilo/ticket concreto).
5. **Si no se publica**: termina ofreciendo ampliar contexto o publicar el resumen, sin más texto.
6. **Si se publica** (acción que modifica estado):
   1. Con los informes previos devueltos por `teams-extractor`, aplica las reglas de «Informes previos» y compón el **borrador** según «Mensaje de publicación». Indica al usuario cuántos resueltos se han omitido.
   2. Comprueba que la puerta de dudas se ha pasado sobre **todo** lo que entra en el mensaje (también hilos que solo entran en la publicación, como resueltos o internos). Muestra al usuario el borrador tal y como se verá en Teams y el **destino exacto**, y pide confirmación con `question`. Cada versión nueva requiere una confirmación nueva.
   3. Solo con un "sí" claro, **publica tú** el texto exacto confirmado en el destino (skill `/product-forge-teams`), tras repetir la comprobación previa. No permitas que el texto cambie entre borrador y envío.
   4. Informa del resultado. Recuerda que los mensajes enviados no se pueden editar ni borrar.

## Formato del informe (escaneo)

**Por defecto el informe es mínimo.** El contexto se da solo si el usuario lo pide. No muestres preview largo ni explicaciones no solicitadas.

Cada hilo o ticket lleva **dos emojis**, siempre **los primeros tras el número de cada línea** y en este orden: 1º criticidad, 2º atendido (significado en [clasificacion.md](clasificacion.md)).

1. Una línea de alcance: canales, rango, zona horaria (`Europe/Madrid`) y nº de hilos relevantes. Indica que Q - Soporte API Storefront y los Imp. XXX se han filtrado por mención a Storefront + URL de API de Producto, y que los hilos que citan un ITSMECOM se han verificado contra Jira por estado y equipo asignado.
2. Tabla resumen por canal **solo sobre pendientes** (🫥 y 🏃‍♂️‍➡️): nº de pendientes y su desglose por criticidad 🔴 🟠 🟡 ⚪ y por atención 🫥 🏃‍♂️‍➡️, solo con los canales que tengan pendientes. Los recuentos se obtienen contando tu clasificación, no se estiman. Incluye ITSMECOM como una fila más.
3. **Pendientes (🫥 y 🏃‍♂️‍➡️)**, ordenados según «Orden», **una sola línea por elemento**: criticidad + atendido · fecha · antigüedad · canal · autor · tema en pocas palabras · URL completa en texto visible. Marca con «(PR abierta)» los hilos del equipo. Separa hilos de Teams, incidencias ITSMECOM y consultas ITSMECOM.
4. No listes por defecto resueltos (✅), informativos, motivos ni observaciones. Añade una única línea final «Omitidos: N resueltos, N informativos, N PR cerradas, N por ITSMECOM cerrado o fuera de Pacman, N ajenos al squad» (contados desde tu clasificación) y avisa solo de limitaciones que afecten al resultado (canal inaccesible, miembros no verificados, truncado, ticket no consultable). El recuento «ajenos al squad» incluye los hilos de Incidencias 🐞 sin mención ni participación del squad.

**Orden dentro de cada bloque** (informe y mensaje): primero por criticidad (🔴, 🟠, 🟡, ⚪) y, dentro de la misma, por atendido (🫥, 🏃‍♂️‍➡️, ✅). A igualdad de ambos, del más antiguo al más reciente.

## Mensaje de publicación (borrador y envío)

- **Título**: primera línea tras el aviso de IA obligatorio (skill `/product-forge-teams`): `**Temas pendientes entre dd/mm/aaaa y dd/mm/aaaa**` (inicio y fin del informe), seguida de línea en blanco. Es la única línea que no es un elemento numerado ni cabecera de bloque.
- Mensaje **conciso**, **un tema por línea en una lista numerada** (`1. `, `2. `…), con las particularidades de formato de `/product-forge-teams`. Sin línea de «Urgente» ni texto adicional.
- **Numeración continua en todo el mensaje:** los elementos se numeran `1.`, `2.`… sin reiniciar entre bloques (el primer número de cada bloque fija el inicio de su lista), para poder referirse a cada tema por su número. Las líneas de ejemplo de este documento usan `- ` solo por brevedad: en el mensaje real llevan número.
- **Cinco bloques**, en este orden, cada uno ordenado según «Orden» y omitido si está vacío: 1º «Hilos abiertos por personas externas» (🫥/🏃‍♂️‍➡️ de Teams); 2º «Incidencias ITSMECOM»; 3º «Consultas ITSMECOM»; 4º «Hilos internos» (hilos del equipo con PR abierta); 5º «Hilos externos resueltos» (✅ iniciados por personas externas). Los bloques 1 a 4 llevan solo pendientes; los ✅ van solo en el 5º.
- **Invariantes por bloque (obligatorios, se comprueban antes de enviar)**:
  - **Bloque 1**: el raíz lo ha escrito alguien **que no es miembro de ProductForge** y el hilo tiene petición viva hacia el squad. Un hilo abierto por un miembro del squad **nunca** va aquí.
  - **Bloque 4**: solo hilos con **al menos una PR en estado `OPEN`**. Un hilo del equipo sin PR abierta no entra (si su causa está fuera, es ✅ omitido; si es una petición interna sin PR, va al informe, no al mensaje). El texto del enlace es **el título de la PR**, sin prefijo de canal.
  - **Bloque 5**: ✅ iniciados por personas externas. Los ✅ de hilos internos no se publican.
  - **Canal**: en los bloques 1 y 5 el texto del enlace lleva el canal real del hilo. Si un hilo está en Incidencias 🐞, se pone «Incidencias 🐞», no el canal donde se cree que debería estar.
- **Hilos de Teams**: `N. <criticidad> <atendido> [título](webUrl) · dd/mm`. En el 1er bloque el texto del enlace empieza por el nombre completo del canal (`[<Canal>: <título>]`, sin sufijo «Canal …»). En hilos del equipo, el texto es el título de la PR (`gh pr view`), la principal si hay varias.
- **Líneas ITSMECOM**: `N. <criticidad> <atendido> [ITSMECOM-N](https://jira.inditex.com/jira/browse/ITSMECOM-N): <título> · dd/mm — <estado>. <descripción>`. El enlace va **solo sobre el ID**; la fecha es la de creación. El estado es «En curso, asignado a <nombre>» o «En cartera, sin asignar». La descripción (ver clasificación) es obligatoria.
- **Resumen de estado**: en TODOS los hilos 🏃‍♂️‍➡️ y ✅ añade tras la fecha ` — <resumen breve>` (ver clasificación). Los 🫥 no llevan resumen.
- **Texto limpio**: cada hilo o ticket aparece una sola vez; sin corchetes (quítalos de títulos y resúmenes) ni textos truncados; mantén una única fuente del texto.
- **Comprobación previa al envío**: valida con regex que cada línea numerada cumple el formato anterior, por ejemplo `^\d+\. (🔴|🟠|🟡|⚪) (🏃‍♂️‍➡️|🫥|✅) \[[^\[\]]+\]\(https://[^)\s]+\)(: [^\[\]]+?)? · \d\d/\d\d( — [^\[\]]+)?$`, y no envíes si alguna falla.
- Avisa de que los mensajes enviados no se pueden editar ni borrar.

### Informes previos

Con los informes `Temas pendientes entre …` de los últimos 7 días que devuelve `teams-extractor`, **omite del 5º bloque los ✅ que ya aparezcan como resueltos** en alguno (identifícalos por `webUrl`/clave). Los hilos todavía abiertos (🫥/🏃‍♂️‍➡️, incluidos ITSMECOM) **se incluyen siempre**, y un hilo que antes estaba pendiente y ahora está resuelto se incluye como resuelto. Si el 5º bloque queda vacío, omítelo. Informa al usuario de cuántos se han omitido y de qué mensaje(s), o de que no había informe previo. Si `teams` no pudo leer el hilo, indícalo como limitación y no omitas nada.

## Reglas

Aplican además tus reglas comunes (castellano, horas en `Europe/Madrid`, no inventar, mostrar limitaciones, confirmación explícita).

- Pasa a los extractores la norma de castellano y la de horas.
- Los extractores son de solo lectura; clasificar y publicar lo haces tú, y publicar solo con confirmación explícita.
- **Eficiencia de lectura (obligatorio):** el barrido tarda ~17-20 s y la resolución de PR ~2 s; el resto del tiempo del informe es lectura del modelo. Lee `indice.txt` una vez, pide el texto íntegro de todos los candidatos en **una sola invocación** de `detalle.py` y no generes volcados intermedios ni releas los JSON. Medido en el informe del 18/10–04/11: sin este flujo se leyeron 550 KB para clasificar 26 KB útiles (el 83 % del texto descartado).
- **ITSMECOM citados: nunca a ojo.** Todo hilo que cite un ticket se cruza contra Jira por **estado** y **`Equipo Asignado`**; las etiquetas no se usan. Un hilo cuyo ticket está en la categoría Done o ya no está en `jsdsoportepacman` **no se lista como pendiente**. Si no se pudo consultar el ticket, dilo como limitación y no apliques la regla.
- **Hilo sin respuestas: lee el raíz antes de clasificar.** Con `n_respuestas = 0` el raíz es el único contenido; decidir por el título es un error. Si el cuerpo no está disponible, marca el hilo «no verificable», nunca 🫥 por defecto.
- **Cierre del squad sin réplica ⇒ ✅.** Si el último mensaje es de un miembro del squad con una acción terminada (desplegado, corregido, mergeado, hecho) y nadie escribe después, el hilo está resuelto aunque el solicitante no haya confirmado. No aplica si el último mensaje del squad deja algo abierto o pregunta algo.
- **Dudas: pregunta SIEMPRE, es una puerta bloqueante.** Antes de presentar el informe o publicar, se pasa el «Control de dudas obligatorio» de `clasificacion.md`: diagnósticos sin acción terminada («no se reproduce»), reglas en conflicto, reaperturas ambiguas, causa en otro equipo sin ubicar o un resumen que solo se sostiene con «seguimos revisando» obligan a preguntar. Prohibido resolver la duda en solitario o dejarla solo en limitaciones.
- **Dudas razonables: pregunta al usuario con enlace.** Ante una clasificación no concluyente, usa `question` con el **enlace completo visible, solo en una línea nueva y sin texto detrás**, para que se pueda verificar en un clic sin que la consola lo parta. Varias dudas van en la misma llamada. No preguntes lo que una regla ya resuelve.
- **Causa fuera de Pacman/Storefront ⇒ resuelto.** Si el squad ubica la causa en otro sistema (Core/Product Core, Adapter, Imagen, Navigation, Grids, Menú, Tags, Search, frontales o infraestructura) y el hilo se escala a ese equipo **sin ninguna petición viva hacia Pacman/Storefront**, el hilo es ✅ y no pendiente, aunque la conversación siga con otros equipos. Solo vuelve a pendiente si alguien reclama explícitamente algo nuestro. Una mera sospecha o un «lo revisamos con ellos» no cierra el hilo. Detalle y ejemplo en [clasificacion.md](clasificacion.md).
- **Hilo del squad que reclama revisión a otro squad ⇒ ✅ omitido.** Si el raíz lo escribe un miembro de ProductForge para pedir a otro equipo que revise lo suyo (jobs en KO por DataGravity o XMedia, datos que llegan mal desde Core…), el hilo no es una petición hacia Producto/Storefront: es trabajo ajeno y **nunca** se lista como pendiente ni como hilo interno. Una nota posterior del propio squad («quedan KOs que limpiar») **no** lo reabre; solo lo reabre una petición al squad desde otro autor.
- **Incidencias 🐞 solo con mención o participación del squad.** En el canal 2 la relevancia es estricta: mención al squad o a un miembro de ProductForge, o participación de un miembro. Sin ninguna de las dos, el hilo es ajeno y se omite citando el squad propietario. Ver [clasificacion.md](clasificacion.md).
- **Acuses ajenos no reabren.** Tras una respuesta concreta de cierre del squad, un «gracias», «lo tenemos en cuenta» o «lo probamos en la próxima ronda» de alguien ajeno **no** devuelve el hilo a pendiente. Solo lo reabre un mensaje que vuelva a reportar el problema, pida algo al squad o contradiga el diagnóstico.

### Presupuesto medido del informe

De dónde se recortó:

| Consumo | Antes | Ahora |
|---|---|---|
| `indice.txt` | 28 KB | 28 KB |
| Detalle de candidatos | 116 KB en **4 llamadas** | ~68 KB en **1 llamada** |
| Hilos de más de 20 respuestas | 67 KB (3 completos) | 8,7 KB (−87 %) |
| Jira (búsqueda + comentarios) | 25 KB en 2 búsquedas | 25 KB en 1 búsqueda |
| Resolución de PR | no se hacía | ~1 KB, 1 llamada |
| Verificación de ITSMECOM citados | no se hacía | ~1 KB, 1 llamada |

No merece la pena, y está medido para que no se reintente: recomprimir los JSON (`indent=1` → plano, 430 → 358 KB) no ahorra nada porque el agente no los lee; recortar el cuerpo del índice a 150 caracteres solo baja un 6 %; y bajar los comentarios de Jira a 2 pierde diagnósticos completos.
