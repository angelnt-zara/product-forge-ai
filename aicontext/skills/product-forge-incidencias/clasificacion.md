   # Criterios de clasificación (temas pendientes)

> Documento de apoyo de la skill `product-forge-incidencias`. Lo aplica **el agente principal** (`product-forge-pana`) sobre los datos objetivos que devuelven los extractores de Teams y Jira. No hay subagente clasificador: la decisión es del principal, que no debe delegarla ni dar por buena ninguna clasificación sin aplicar estos criterios.

A cada hilo o ticket se le asigna: criticidad, estado de atención, si es informativo, si se omite (con motivo) y, según el caso, un resumen de estado o una descripción.

## Entrada

- Lista de miembros de ProductForge (de `team.adoc`, más Elias Ferreiro Borreiros).
- Datos devueltos por los extractores, sin resumir ni recortar: hilos de Teams con respuestas y estado de las PR, y tickets ITSMECOM con comentarios.

Si falta información para decidir con rigor (no queda claro si la última respuesta del squad es concreta, si un ticket sigue vigente, si un hilo cita un ticket que no vino en la lista de abiertos…), **no la inventes**: pídesela al extractor correspondiente reutilizando su sesión. Si tras ello persiste una duda material, pregunta al usuario con `question`.

**Lectura fallida ≠ sin respuestas:** si un extractor informa de que no pudo leer las respuestas de un hilo (error, 404, formato inesperado), no aceptes `respuestas: []`. Devuélvele la petición para que reintente y no clasifiques ese hilo hasta tener las respuestas. Si el reintento también falla, márcalo como «no verificable» y muéstralo como limitación, nunca como 🫥 por defecto.

## Relevancia del hilo

Solo se clasifican hilos que mencionan al squad (etiqueta de ProductForge o de sus equipos, o su nombre) o que lo implican por el canal. Un hilo que solo etiqueta a otros equipos no es del squad: no cuenta como pendiente. Anótalo como limitación si la mención es dudosa.

**Canal Incidencias 🐞 (canal 2): relevancia estricta.** En este canal **no basta** con que el hilo «implique» al squad por el canal. Solo se clasifica si se cumple **al menos una** de estas dos condiciones:

1. **Mención directa al squad**: el raíz o alguna respuesta menciona la etiqueta o el nombre del squad (`ProductForge`, `Store Front Producto`, `ComercialProducto`, `ComercialProductoStore`, `Pacman Contributors`, `Pacman Products`) **o a un miembro de ProductForge** —lista de `team.adoc` § ProductForge, más Elias Ferreiro Borreiros—, tanto en `mentions` como en el texto del mensaje.
2. **Participación del squad en un hilo ajeno**: el raíz lo escribió **alguien de fuera** y **al menos un miembro de ProductForge** ha respondido.

Si **ninguna** se cumple, el hilo **se omite** como ajeno (motivo «sin mención ni participación del squad») y se cuenta en «Omitidos». Cuando el hilo lo atiendan personas de otro squad identificables en `team.adoc`, cita el squad propietario en el motivo: es la señal de a quién pertenece el asunto. Un hilo así no es informativo ni pendiente: no es nuestro.

> **Ojo: que el raíz lo escriba un miembro del squad NO basta para entrar.** La condición 2 exige que el raíz sea de alguien **de fuera**. Antes se contaba al autor del raíz como «participación del squad», y por ahí entraban hilos que un miembro abría en este canal para pedir a **otro** equipo que revisara lo suyo. Caso real (05/11/2026): «Problemas con el cambio del filtro Tipo de grid en el buscador desde la página de Grids», abierto por un miembro del squad mencionando solo a Grids («Grids ¿le podéis echar un ojo?»). Se clasificó como 🟠 pendiente propio cuando era trabajo de Grids.
>
> El extractor marca estos casos con `reclama_a_otro = true` y los campos `autor_raiz_es_squad` y `menciones_otras`; el índice los muestra como `[raizAUTOR, otro=Grids, RECLAMA_A_OTRO]`. Si `reclama_a_otro` es cierto, se omite como ✅ con motivo «causa fuera de Pacman, reclamada por el squad», sin valorar criticidad.

- **Los hilos sin mención no se tiran en silencio.** Si un hilo de este canal no cumple la relevancia estricta, no se descarta sin más: se cuenta en la línea final de «Omitidos» y, si el título sugiere que podría ser de Producto/Storefront, se pregunta al usuario (ver «Dudas razonables: pregunta con enlace»).

- **Excepción que prevalece**: que un miembro del squad participe **no** convierte en pendiente un hilo cuya causa está fuera y en el que el squad solo reclama revisión a otro equipo. Se aplica entonces la regla de «Hilos cuya causa está fuera de Pacman/Storefront», incluido el subcaso del hilo abierto por un miembro del squad para pedir a otro squad que revise lo suyo: **✅ omitido**, nunca pendiente.
- **Cuidado con los hilos transversales**: en Incidencias 🐞 es habitual que el raíz lo abra una persona de Cross con varios squads en su ámbito (p. ej. PM Vertical Comercial) y que el asunto acabe en Tágticos, Grids o MenuDelux. Si nadie de ProductForge intervino y el contenido no pide nada sobre Producto/Storefront, el hilo es ajeno aunque su autor figure en `team.adoc` en otra sección.

**Canales de soporte de API e implantación (Q - Soporte API Storefront e Imp. Bershka / Lefties / Massimo Dutti / Oysho / Pull and Bear / Stradivarius / Zara Home, todos externos):** en estos canales convive funcionalidad de muchos equipos, así que la relevancia la decide el **filtro reforzado del extractor**: el hilo debe mencionar **Storefront** (o una etiqueta del squad) **y** aportar al menos una **URL de API de Producto** con segmento `/product`, `/products` o `/productsArray` en el path. Los dos requisitos son obligatorios y se evalúan sobre el hilo completo (raíz o respuestas).

Los demás canales externos (B - Gestión incidencias Tecnología, P - Dudas técnicas, PRO Validación Pruebas, Incidencias Entornos Previos) se filtran **solo por mención al squad**, igual que el canal 1 (SQUAD Product Forge 🛠️) y PACMAN Contributors: no les exijas URL de Producto. El canal Incidencias 🐞 tiene además la regla estricta del párrafo anterior.

- Si el extractor devuelve un hilo que cumple el filtro pero al leerlo el endpoint citado resulta **no ser de Producto** (por ejemplo, `/stores/{id}/menu`, `/tags`, `/grids`, `/checkout`, o una pantalla del frontal de Pacman), **no es del squad**: omítelo como informativo/ajeno y anótalo en una línea.
- Al contrario: si un hilo de estos canales trata claramente un problema de Producto pero el extractor lo dejó en `descartadosPorFiltro` por no encajar en la regla literal (p. ej. la URL viene partida o sin esquema), **no lo rescates por iniciativa propia**: indícalo como limitación y, si es material, pide al extractor que lo recupere con su sesión.
- En estos canales es frecuente que el hilo del rollout de una cadena se abra semanas antes y siga vivo. Clasifícalo por su **última actividad**, no por la fecha del raíz, y ten en cuenta la antigüedad real al valorar criticidad.

### Destinatario del hilo en los canales 8-15: no todo «Storefront» es nuestro

El filtro reforzado tiene un punto ciego que produjo **cuatro falsos positivos reales** en el informe del 18/10–09/11/2026: «Storefront» es el nombre genérico de la familia de APIs que también consumen Grids y Navigation, y además forma parte del nombre de **otro equipo** («Storefront Parrillas»). Hilos dirigidos a Grids o a Menú entraban como pendientes del squad.

El extractor aplica ahora una decisión de **tres estados** (`destinatario_canales_externos`), **solo** cuando el hilo no menciona al squad ni tiene participación de un miembro de ProductForge:

| Estado | Condición | Qué haces |
|---|---|---|
| **mantener** | El hilo menciona al squad, o un miembro de ProductForge participa | Se clasifica normal. **Esta condición prevalece siempre** |
| **excluir** | Sin mención ni participación, y el raíz se dirige a otro squad de PACMAN (`pacman menú`, `menú pacman`, `menudelux`, `gridsf`, `comercialgrids`, `comercialparrillas`, `navigasf`, `tágticos`, `searchsf`…) o el hilo dice «Storefront <equipo ajeno>» | Omitir como ajeno, citando el squad real |
| **preguntar** | Sin mención, sin participación y sin destinatario identificable | **Preguntar al usuario con el enlace completo**, nunca decidir en solitario |

- **La participación prevalece sobre todo lo demás.** Hay hilos reales que solo se salvan por ahí: «STOREFRONT // Medidas Extra - detail» no menciona al squad, pero responde Adrián Rábade (PACMAN-35944). Sin esta salvaguarda se perdería.
- **El patrón exige el sintagma pegado** «Storefront <equipo>», nunca la palabra suelta. Medido: aceptar `\bgrids\b` suelto se comía dos hilos reales de Producto («extra-detail by reference», «Productos con nombres diferentes en storefront»), porque en hilos de Producto se habla de grids constantemente.
- **Los «preguntar» no se excluyen ni se dan por pendientes**: van a `excluidos` con `dudoso: true` y el informe los consulta con `question`. Es la política acordada el 09/11/2026: ante la duda, pregunta con enlace.
- **La URL no basta para decidir.** Un listado de categoría (`/category/{id}/product?...`) sigue pasando el filtro de URL porque estrecharlo rompía casos legítimos; el destinatario es quien descarta el hilo.
- **No se usan etiquetas** de Jira ni de Teams para decidir, ni siquiera cuando aciertan (`C-PacmanGrids` en ITSMECOM-5892704 y ITSMECOM-5898095). La regla del flujo es que un caso se decide por estado y equipo asignado; aquí, por a quién se dirige el hilo.

## Reglas de obligado cumplimiento antes de clasificar

Estas dos comprobaciones van **antes** de la criticidad y del estado de atención. Saltárselas produjo dos errores reales el 05/11/2026, ambos detectados por el usuario y no por el agente.

### 1. Hilo sin respuestas ⇒ leer el raíz. Nunca clasificar por el título

Si `n_respuestas = 0`, el **único** contenido del hilo es el mensaje raíz. Está prohibido decidir relevancia, criticidad o estado mirando solo el título.

- El índice incluye el cuerpo del raíz en la columna del último mensaje cuando no hay respuestas, y `detalle.py` lo imprime en la línea `RAÍZ:`.
- Si el raíz **no** aparece en el detalle (extracción antigua o fallo de lectura), no lo supongas: vuelve a pedir el detalle con `detalle.py` y, si sigue faltando, marca el hilo como **no verificable** en las limitaciones. Nunca como 🫥 por defecto.
- Caso real: «Problemas con el cambio del filtro Tipo de grid en el buscador desde la página de Grids» tiene 0 respuestas; su raíz pide a Grids que lo revise. Por el título parecía una incidencia nuestra y se publicó como 🟠 pendiente.

### 2. Cierre del squad sin réplica posterior ⇒ ✅ resuelto

Si el **último** mensaje del hilo es de un miembro de ProductForge y contiene una **acción terminada** —«ya está desplegado», «desplegado en PRO», «corregido», «mergeado», «subido», «hecho», «resuelto», «ya lo veo ok»— y **no hay ningún mensaje después**, el hilo es **✅ resuelto**, aunque el solicitante no haya confirmado ni nadie haya validado en la siguiente ronda.

- La acción del squad está completa; la validación pendiente es del solicitante, no nuestra.
- El resumen de estado recoge qué se hizo y, si procede, que queda pendiente de verlo en la próxima prueba.
- No se aplica si el último mensaje del squad **deja trabajo nuestro abierto** («estamos revisándolo», «lo miro», «lo abordaremos cuando tengamos capacidad»): entonces sigue pendiente.
- **Pregunta del squad que no bloquea nuestro trabajo ⇒ ✅ por nuestro lado.** Si el último mensaje del squad **ya responde a lo que se consultó** (da el dato, la alternativa o el diagnóstico) y solo añade una pregunta al solicitante para valorar un desarrollo opcional o futuro («¿lo necesitáis también para bundles?», «si preferís que lo devuelva nosotros, habría que desarrollarlo»), la pelota está en el solicitante: el hilo es ✅ y el resumen lo dice («respondido; pendiente de que X confirme si necesita…»). Caso real (10/11/2026): «Consulta sobre disponibilidad del campo addToCartDisabled en Producto», donde David explicó que storefront no lo expone y que se deriva del `type`, y preguntó si se necesita en bundles; se publicó como 🟡 🏃‍♂️‍➡️ por error.
- Sí sigue pendiente si la pregunta del squad **es necesaria para poder avanzar nosotros** (falta un dato para reproducir o corregir: «¿podéis pasarme un ejemplo?») y el solicitante no ha respondido: ahí también la pelota está fuera, pero no se ha dado respuesta de fondo; no se marca ✅ y, si hay duda de cuál de los dos casos es, va al control de dudas.
- Caso real: «Errores 5xx y 4xx en Irlanda OY». Último mensaje de Neto: «Ya quedó desplegado en PRO. En la próxima prueba lo deberíamos ver reflejado». Se publicó como 🔴 pendiente en dos informes seguidos.

## Control de dudas obligatorio (puerta antes de presentar o publicar)

Preguntar ante la duda **no es opcional ni queda a criterio del momento**. Tras clasificar y **antes** de mostrar el informe o de redactar cualquier borrador de publicación, recorre todos los elementos y construye la lista de dudas. Es una **puerta**: sin ella resuelta no se presenta ni se publica nada.

Un elemento es dudoso, y por tanto se pregunta, si se cumple **al menos una**:

1. La última aportación del squad es un **diagnóstico o una conclusión sin acción terminada** («no se reproduce», «creo que es de X», «funciona por nuestro lado», «no lo vemos») y nadie del solicitante ha confirmado ni cerrado. No es un cierre ✅ ni una petición viva clara.
2. Dos reglas apuntan a resultados distintos (p. ej. «respuesta concreta del squad» vs. «sigue abierto el ticket»), o hay que aplicar «en caso de duda» para decidir.
3. No queda claro si el último mensaje ajeno **reabre** o solo **acusa recibo**.
4. La pelota parece estar en otro equipo pero no hay ubicación cerrada ni petición explícita hacia Pacman/Storefront.
5. El resumen de estado que escribirías **no se sostiene con una frase concreta** del hilo (si tienes que suavizarlo con «seguimos revisando» u otra fórmula genérica, es señal de duda).
6. Un hilo `dudoso: true` o excluido por relevancia cuyo asunto podría ser de Producto/Storefront (ver más abajo).

Cómo se aplica:

- **Una sola llamada `question`** con todas las dudas (formato de la sección siguiente, con el enlace en línea propia). Opciones concretas y excluyentes, con la clasificación que aplicaría a cada una.
- **Prohibido** resolver una duda «a favor de pendiente» o «a favor de resuelto» sin preguntar, y prohibido dejarla solo anotada en limitaciones.
- Si no hay dudas, no preguntes: anota en una línea «Sin dudas de clasificación» en el alcance para que conste que la puerta se ha pasado.
- Las respuestas del usuario se recuerdan durante la sesión: no repreguntes por el mismo hilo en el mismo estado.
- Una publicación **nunca** incluye un elemento cuya duda no esté resuelta.

Caso real que originó esta puerta (10/11/2026): hilo «OY productsf no devuelve el detalle de producto commercialDetail». Un miembro del squad escribió «no se reproduce el caso reportado ni ninguno de los del ticket»; se publicó como 🔴 🏃‍♂️‍➡️ con el resumen «seguimos revisando» sin preguntar. Era el criterio 1 y el 5.

## Dudas razonables: pregunta con enlace

Cuando la clasificación de un hilo o ticket no sea concluyente —no queda claro si pide algo al squad o a otro equipo, si la última respuesta cierra o solo acusa recibo, o si un hilo sin mención es realmente de Producto—, **no decidas por tu cuenta ni lo escondas en las limitaciones**: pregunta al usuario con la herramienta `question`.

Requisitos de la pregunta:

- **Una pregunta por hilo dudoso**, con las opciones concretas y excluyentes (`Incluir como pendiente`, `Omitir como ajeno`, `Omitir como resuelto`).
- **Siempre el enlace completo en el texto visible** (`webUrl` del hilo, o la URL del ticket en Jira), para que se pueda verificar en un clic. No vale «el hilo del filtro de grids»: hay que poder abrirlo sin buscarlo.
- **El enlace va SIEMPRE solo en una línea nueva** (salto de línea antes y nada después, ni punto final ni paréntesis). Los `webUrl` de Teams son muy largos y, si van al final de una línea de texto, la consola los parte y no se abren bien. Aplica a todo texto de `question` (enunciado y descripciones de opciones). Estructura: primero el enunciado con la duda, línea en blanco y la URL sola en su línea.
- Incluye en el enunciado el dato que causa la duda: quién abrió el hilo, a quién menciona y qué dice el último mensaje.
- Si hay **varios** hilos dudosos, pregunta por todos en la **misma** llamada (`questions` admite varias), no en tandas.
- No preguntes lo que una regla ya resuelve: la duda debe ser material. Aplicar una regla clara no requiere confirmación.

### 3. Hilos excluidos por relevancia: revísalos y pregunta si hay duda

El extractor guarda en `excluidos` (dentro del JSON de cada canal) los hilos descartados por no cumplir la relevancia, con su `motivo`, `webUrl`, `texto_raiz`, `autor_raiz_es_squad` y `menciones_otras`. **No los ignores**: al cerrar la clasificación, recórrelos y decide.

- Si el motivo es `causa fuera de Pacman, reclamada por el squad`, van directos a «Omitidos» como ajenos. No preguntes: la regla es clara.
- Si el motivo es `sin mención ni participación del squad` **y** el título o el raíz sugieren que el asunto es de Producto/Storefront (parrillas, precios, visibilidad, bundles, extra-detail, PDP, API de producto), **pregunta al usuario** con `question` y el **enlace completo** del hilo. Es un posible punto ciego de la regla estricta y la decisión es suya.
- Si el asunto es claramente de otro ámbito (menú, navegación, buscador, wishlist, checkout, imágenes), no preguntes: cuenta el hilo en «Omitidos» y sigue.

No preguntes por todos: solo por los que de verdad puedan ser nuestros. Una pregunta con demasiadas opciones no se lee.

## Hilos que citan un ITSMECOM: verificación cruzada obligatoria

Un caso puede quedar resuelto en su Jira sin que nadie deje feedback en el hilo de Teams, y también puede haberse reasignado fuera de Pacman. En los dos casos el hilo parece pendiente sin serlo. Por eso, **todo hilo que cite un ITSMECOM —en el título o en cualquier respuesta— se verifica contra Jira antes de clasificarlo**.

**La verificación se hace SOLO por estado y equipo asignado. Las etiquetas no cuentan**, ni a favor ni en contra: da igual `C-PacmanProduct`, `C-StoreFront`, `C-ProductForge`, `ASIGNACION_INCORRECTA` o cualquier otra; no se usan para decidir ni para matizar.

| Situación del ticket | Decisión sobre el hilo |
|---|---|
| Estado en la categoría **Done** (Resuelta, Cerrado, Cancelado) | **Omitir** (motivo «ITSMECOM cerrado»). |
| Abierto pero `Equipo Asignado` **distinto** de `jsdsoportepacman` | **Omitir** (motivo «ITSMECOM fuera de Pacman»). |
| Abierto y `Equipo Asignado` = `jsdsoportepacman` | Se clasifica con los criterios normales. |
| No se pudo consultar | **No apliques la regla** sobre ese hilo: clasifícalo normal y declara la limitación. |

- **Hilo con varios ITSMECOM:** se omite solo si **todos** están cerrados o fuera de la cola de Pacman. Basta un ticket abierto y asignado a Pacman para mantenerlo; en ese caso se indica cuál sigue vivo.
- **Qué es «Pacman» aquí:** la cola de soporte del squad, `Equipo Asignado` = `jsdsoportepacman` (se muestra como «N2 Pacman»), que es la misma que filtra la consulta principal de abiertos. Un ticket en otro equipo —aunque sea otro equipo de Pacman, como `jsddesarrollopacmanproduct` («N3 Pacman»)— **se omite**, citando el equipo real; no es cartera de soporte del squad.
- La verificación se aplica **antes** de la criticidad y del estado de atención: un hilo omitido por este motivo no cuenta como pendiente, ni como informativo, ni como resuelto. Va a la línea final de «Omitidos» con su propio recuento.
- El estado y el equipo se citan tal cual los devuelve Jira («Resuelta», «Cerrado», `Equipo Asignado = <nombre>`). No se interpreta el estado a partir de las etiquetas ni de los comentarios.
- Los hilos cuyo único ITSMECOM aparece en un resumen automático del bot (varios tickets en un mensaje de reunión) no son hilos de incidencia: se omiten como informativos, no por esta regla.

## Quién cuenta como «respuesta del squad»

Se considera dada respuesta si **al menos un miembro de ProductForge** ha respondido en el hilo con **una respuesta concreta**.

1. **Respuesta concreta**: aporta información, diagnóstico, solución, decisión, enlace a un Jira/PR, petición de datos específica o indica que ya está corregido/desplegado.
2. **No cuenta**: «lo revisamos», «lo miramos», «ahora lo vemos», «tomo nota», «+1», «👍», «gracias», «cc @alguien» sin contenido, o reacciones. Si el único mensaje del squad es de este tipo, el hilo sigue **pendiente**.
3. Las respuestas de personas ajenas al squad **no** cierran el hilo.

### Mensajes ajenos que no reabren un hilo cerrado

La simetría de la regla anterior es obligatoria: si «lo revisamos» no basta para cerrar, un acuse ajeno no basta para reabrir. Cuando el squad ya ha dado una **respuesta concreta de cierre o solución**, los mensajes posteriores de personas ajenas al squad **no reabren** el hilo si se limitan a:

- confirmar o agradecer: «gracias», «perfecto», «ok», «mil gracias», «queda corregido», «ya funciona», «lo veo bien», «validado»;
- acusar recibo o anunciar seguimiento propio: «lo tenemos en cuenta», «lo añadimos para la próxima prueba», «lo probamos en la siguiente ronda», «lo revisamos por nuestra parte», «te confirmamos»;
- cerrar formalmente: añadir `[CLOSED]` al título, decir que se cierra la incidencia o marcar el hilo como resuelto.

Ese tipo de mensaje **confirma** la acción del squad, no pide nada nuevo: el hilo es **✅ resuelto** y el resumen de estado recoge la confirmación.

**Sí reabren el hilo** los mensajes ajenos que:

- vuelven a reportar el mismo problema o uno nuevo («sigue fallando», «nos vuelve a pasar», «ahora sale otro caso»);
- piden algo concreto al squad —un dato, un cambio, una validación nuestra, un fix de nuestro lado— o hacen una pregunta directa sobre nuestro ámbito que se queda sin respuesta;
- contradicen el diagnóstico o devuelven la pelota a Producto/Storefront.

La duda se resuelve a favor de **resuelto** solo cuando el mensaje ajeno es inequívocamente de confirmación; si es ambiguo, el hilo va al control de dudas y se pregunta al usuario.

## Hilos iniciados por miembros del squad (peticiones de revisión de PR)

- El estado de las PR **lo aporta `prs.py`**, no se supone: cada hilo trae su campo `prs` y el script lo resuelve en lote. Si una PR sale como `DESCONOCIDO` (no se pudo consultar), **no apliques esta regla** y decláralo en limitaciones.
- Si **todas** las PR del hilo están cerradas (`MERGED` o `CLOSED`), el hilo se da por solucionado: **omitir** (motivo «PR cerradas»). Una PR aprobada pero `OPEN` no está cerrada.
- Si alguna PR sigue `OPEN`, el hilo es **interno pendiente**: 🫥 si no hay respuesta concreta, 🏃‍♂️‍➡️ si el squad ya contestó algo concreto y queda una pregunta sin atender. Indica qué PR sigue abierta.
- Sin enlace a PR se clasifica con los criterios normales; los resueltos de miembros del squad se omiten.
- Si el parámetro «PRs cerradas» de la skill está activo, no omitas por este motivo.

## Hilos iniciados por personas externas con PR

No somos responsables del trabajo de squads ajenos: nuestro trabajo termina al revisar el hilo o la PR.

**Regla obligatoria (sin excepciones ni criterio propio):** en un hilo abierto por un externo con **todas** las PR enlazadas aprobadas (`reviewDecision` = `APPROVED` o aprobación explícita de un miembro del squad) el hilo es **✅ resuelto**, aunque la PR siga `OPEN`, sea urgente, el último mensaje sea del squad o haya riesgo de despliegue. Esta regla **prevalece** sobre «en caso de duda, pendiente» y no se plantea al usuario. En el resumen de estado indica «PR aprobada por X, pendiente de merge/despliegue» si procede. Un hilo con PR aprobada pero con una pregunta o petición posterior del solicitante sin atender sigue siendo 🏃‍♂️‍➡️.

Si alguna PR no está aprobada, el hilo sigue pendiente (🫥 o 🏃‍♂️‍➡️ según haya respuesta concreta del squad). El estado lo aporta `prs.py`; si una PR sale `DESCONOCIDO`, trátala como no aprobada y declara la limitación.

## Hilos cuya causa está fuera de Pacman/Storefront (escalados a otro equipo)

Nuestro trabajo termina donde acaba nuestro ámbito: si la causa del problema está en otro sistema y el hilo se escala a ese equipo, **el hilo es ✅ resuelto**, aunque la conversación siga viva con otros equipos. Lo que decide no es quién escribió la última respuesta ni quién tiene la última palabra, sino **dónde está ubicada la causa y si alguien sigue reclamando algo a Pacman/Storefront**.

- **Cierra el hilo (✅, motivo «causa fuera de Pacman»)**: un miembro del squad ubica la causa en un sistema ajeno al ámbito de Productos —Core/Product Core, Product Adapter, Imagen/XMedia, Navigation, Grids, Menú, Tags, Search, frontales, infraestructura o el puesto de trabajo del usuario— y la conversación pasa a ese equipo **sin que quede ninguna petición abierta hacia Pacman/Storefront**. Las respuestas posteriores de otros equipos, del solicitante o de bots **no lo reabren**: son seguimiento de un caso que ya no es nuestro.
- **Hilo abierto por un miembro del squad para reclamar revisión a otro squad (✅ omitido, nunca pendiente)**: si el raíz lo escribe un miembro de ProductForge y lo que pide es que **otro** squad revise lo suyo —por ejemplo, jobs de Products que caen en KO por fallos de DataGravity o XMedia, o datos que llegan mal desde Core—, el hilo es trabajo **ajeno** aunque se haya abierto desde nuestro canal. No es una petición hacia Producto/Storefront, sino una petición nuestra hacia otros; se da por resuelto cuando el equipo destino responde, y se **omite** con motivo «causa fuera de Pacman, reclamada por el squad». Nunca se lista como pendiente ni como hilo interno.
  - **Una nota del propio squad no reabre**: que un miembro de ProductForge escriba después «quedaron KOs que hay que revisar/limpiar» o similar **no** es una petición de nadie hacia nosotros, es una anotación de seguimiento interno. Solo reabre una petición dirigida al squad **desde otro autor** (el solicitante o el equipo destino) que reclame algo de nuestro ámbito.
  - La respuesta del equipo destino —«me encargo de esos jobs», «le echo un ojo»— **cierra** el hilo: la causa está fuera y ya tiene dueño.
- **Reabre el hilo (🫥/🏃‍♂️‍➡️, criticidad normal)**: un mensaje posterior **de otro autor** —el solicitante, otro equipo— que **reclama explícitamente algo a Pacman/Storefront** —pide un dato, un cambio, una validación, un fix de nuestro lado, o pregunta por nuestro ámbito y se queda sin respuesta—. Entonces vuelve a ser pendiente del squad y se clasifica con los criterios habituales. Un acuse, un agradecimiento o un cierre ajeno **no** lo reabre (ver «Mensajes ajenos que no reabren un hilo cerrado»), y una anotación del propio squad tampoco.
- **No cierra el hilo** que el squad solo **sospeche** o **apunte** a otro equipo sin establecerse la ubicación: «creo que es de Core», «revisamos con ellos», «les avisamos». Eso es 🏃‍♂️‍➡️ mientras no haya ubicación cerrada ni petición posterior nuestra.
- **Diagnóstico en disputa**: si el squad apunta a un sistema ajeno y ese equipo devuelve la pelota a Producto, o nadie asume la causa, es una duda material: va al control de dudas y se pregunta al usuario con el enlace.
- **Ubicación parcial**: si el hilo tiene varias peticiones y solo una queda fuera de Pacman, se cierra únicamente la parte externa; si queda cualquier acción nuestra viva, el hilo sigue pendiente.
- En el **resumen de estado** indica el equipo destino y el motivo, sin corchetes: «causa en Core-Legacy, escalado a Product Core; pendiente cargar el catentry en DB2». Nunca lo dejes como pendiente por el solo hecho de que el hilo siga con mensajes.
- **No aplica a ITSMECOM**: en los tickets manda el estado y el `Equipo Asignado` en Jira (ver «Hilos que citan un ITSMECOM»), no la lectura del hilo.

Ejemplo de referencia: «[ZA] Producto sin xmedia». El squad diagnosticó una inconsistencia Core-Legacy por un rollback en DB2 y la conversación pasó a los equipos de Core; nadie volvió a pedir nada a Pacman/Storefront, así que el hilo es ✅ resuelto, no 🏃‍♂️‍➡️, aunque siga habiendo mensajes y una carga pendiente en DB2 que no es nuestra.

## Estado de atención (2º emoji)

| Emoji | Estado | Hilos de Teams | ITSMECOM |
|-------|--------|----------------|----------|
| 🫥 | **No atendido** | Ninguna respuesta concreta de un miembro de ProductForge. | Sin asignar o no en progreso (En Cartera). |
| 🏃‍♂️‍➡️ | **Atendido** (en curso) | Hay respuesta concreta del squad pero el hilo sigue abierto (el último mensaje es una nueva pregunta, petición o queja del solicitante sin contestar, o queda trabajo pendiente). | Asignado y En Curso. |
| ✅ | **Resuelto** | Hay respuesta concreta de un miembro de ProductForge y los mensajes posteriores son acuses, confirmaciones o cierres ajenos, no peticiones nuevas. | Resuelto o cerrado. |

- **Los acuses ajenos no reabren**: tras una respuesta concreta de cierre del squad, un «gracias», un «lo tenemos en cuenta» o un «lo probamos en la próxima ronda» de una persona ajena **no** devuelve el hilo a 🏃‍♂️‍➡️; se queda ✅. Detalle de qué sí reabre en «Quién cuenta como respuesta del squad».
- En caso de duda entre resuelto y pendiente **no decidas en solitario ni lo dejes «anotado»**: va al control de dudas (ver «Control de dudas obligatorio») y se pregunta al usuario. Solo si el usuario no puede responder, se clasifica como pendiente y se declara en limitaciones. Excepción: la regla de PR aprobada, que ya está resuelta y no se pregunta.
- **Informativo vs petición:** un aviso FYI sin petición accionable es **informativo** (⚪, no se cuenta como pendiente). Un aviso con pregunta o petición de apoyo sin responder es una **petición** (🫥). Lee el cuerpo completo antes de marcar informativo.
- Un ticket ITSMECOM cuyos últimos comentarios indican que ya está corregido y solo falta cerrar se mantiene pendiente, se anota en el motivo y no se infla su criticidad.
- Si el ticket de Jira citado en un hilo figura resuelto o cerrado, **el hilo se omite** por la regla de verificación cruzada (ver «Hilos que citan un ITSMECOM»), no se lista como pendiente.

## Criticidad (1º emoji)

| Emoji | Nivel |
|-------|-------|
| 🔴 | Urgente |
| 🟠 | Importante |
| 🟡 | Baja |
| ⚪ | Nula |

Combina estos factores. **Los topes (entorno y tipo) prevalecen siempre** sobre la prioridad del canal, la afectación y la prudencia:

1. **Prioridad del canal** donde se reporta (el scope —interno/externo— es contexto de quién escribe, no un factor de criticidad):
   1. PRO Validación Pruebas (externo): siempre 🔴.
   2. B - Gestión incidencias Tecnología (externo): siempre 🔴.
   3. Incidencias 🐞 (interno): 🔴 o 🟠 según el impacto.
   4. SQUAD Product Forge 🛠 (interno): según el contenido, cualquier nivel.
   5. P - Dudas técnicas (externo): normalmente consultas (🟡/⚪).
   6. Incidencias Entornos Previos (externo): problemas de PRE, 🟡 o ⚪.
   7. PACMAN Contributors (interno): normalmente consultas o problemas menores, 🟡 o ⚪.
   8. Q - Soporte API Storefront (externo): normalmente consultas de integración (🟡/⚪); sube a 🟠/🔴 si es un bug de API de Producto con afectación en PRO o STAGE.
   9. Imp. Bershka / Lefties / Massimo Dutti / Oysho / Pull and Bear / Stradivarius / Zara Home (externos): el canal no fija el nivel; decide el contenido (entorno, tipo y afectación). Un bloqueo de la implantación de una cadena en PRO/STAGE es 🟠 como mínimo y 🔴 si compromete una fecha de salida.
2. **Entorno (tope):** PRE y entornos previos (PRE, PREINT, INT) siempre 🟡 o ⚪. **STAGE es producción, no un entorno previo**: no aplica este tope y se clasifica como PRO.
3. **Tipo de petición (tope):** una consulta o solicitud de información siempre 🟡 o ⚪. Un bug es como mínimo 🟠 y pasa a 🔴 si apremia corregirlo (fecha límite cercana, campaña, evento como Double 11…).
4. **Afectación:** una afectación grave (usuarios, ventas, PRO degradado) es 🔴.

### ITSMECOM

Mismos factores sobre el ticket: Incidente = bug; Solicitud de servicio = consulta; entorno y afectación según el ticket y, sobre todo, sus **últimos comentarios**.

- **Consultas (Solicitud de servicio):** SIEMPRE 🟡 o ⚪, nunca 🔴 ni 🟠, aunque sea PRO, tenga prioridad A o lleve mucho tiempo abierta. 🟡 si la prioridad de Jira es A, B o C; ⚪ si es D o no hay prioridad.
- **Incidentes:** como mínimo 🟠; 🔴 si apremian o hay afectación grave; en PRE, tope 🟡/⚪.
- **Ya corregido:** si los comentarios indican que la causa está corregida y solo falta cerrar, no lo marques 🔴 y di por qué.
- No inventes la afectación. Si faltan datos, elige el nivel que mejor se justifique con los disponibles y anótalo en una línea; la prudencia nunca anula los topes.

## Salida de la clasificación

Por cada elemento, anota (para ti, no se muestra salvo petición): `id`, tipo (hilo externo / hilo interno / ITSMECOM-incidente / ITSMECOM-consulta), criticidad, atendido, informativo, omitir (con motivo) y un motivo breve que cite el factor o tope aplicado.

- Hilos 🏃‍♂️‍➡️ y ✅: **resumen de estado** (la solución en los resueltos, aunque la dieran otros equipos o el autor cerrase el hilo; lo pendiente en los de seguimiento), sin corchetes.
- ITSMECOM: **descripción** breve del problema, sacada de los últimos comentarios o, si no hay, de la descripción; sin corchetes ni datos inventados.
