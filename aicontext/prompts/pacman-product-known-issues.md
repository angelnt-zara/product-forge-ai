# Pacman Products: errores conocidos

Fuente única de verdad de los errores conocidos de `MICPCPRODS`. La usan los subagentes `product-forge-pana-logs` y `product-forge-pana-jobs`, y el agente principal `product-forge-pana`.

Cada entrada describe **una causa única**, sin distinguir si se observa en logs o en jobs/eventos: un error en un job va acompañado de logs de error y ambos delatan el mismo problema. Los jobs/eventos solo dejan constancia del mensaje de error principal; los logs aportan la traza completa y más contexto. Por eso, cuando una comprobación necesita más información de la que muestra el job, se deja indicada en **Comprobación ampliada**: se hace consultando los logs (`full_message`, `Caused by`, mismos identificadores y franja).

**Solo se añaden o modifican entradas tras instrucción explícita del usuario.** Se puede sugerir añadir una, pero nunca se añade por iniciativa propia. Toda entrada nueva debe indicar su **impacto**; si no se indica, pregúntalo.

## Cómo usar este catálogo

### Niveles de impacto
El impacto indica si el error señala un problema latente sobre el que el usuario debería actuar.
- **alto / medio:** se notifican siempre, en una sección propia "Errores conocidos de impacto medio/alto" (firma, volumen, tenants, primera/última ocurrencia, alcance de datos), después de los no conocidos y antes de los de impacto bajo. No se ocultan.
- **bajo:** errores "normales" a los que no hay que prestar atención. Solo aparecen en una lista muy breve de conocidos. **Excepción obligatoria:** si dejan jobs/eventos en KO, se advierte igualmente (ver siguiente regla).

### Regla de afectación a jobs/eventos (obligatoria al presentar el informe)
Un error de impacto bajo que **deja jobs o eventos en KO** no se reduce a una línea en el bloque 5 del informe ("Otros errores conocidos de impacto bajo"). Se marca con ⚠️ al inicio de ese bloque, con: error, tenants, nº de jobs/eventos, estado (KO), attempt y si se reintentan solos o requieren acción.
- Cruza ambas fuentes: un error de impacto bajo visto en logs cuya consecuencia son jobs/eventos en KO entra en esta regla (p. ej. un redespliegue que deja eventos sin completar).
- Si hay jobs/eventos en `TO_RETRY` por este error y se supera el umbral de acumulación, además se informa en el bloque "Alta carga de reintentos".
- Si no hay jobs/eventos afectados, se mantiene como una línea breve.
- Excepción: las entradas con instrucción expresa de omisión (p. ej. `UnableToExportLiveLegacyException` con `attempt` = 1) siguen omitiéndose.

### Jobs/eventos en `TO_RETRY`
- Un job/evento en `TO_RETRY` **no es un error no conocido**, aunque su error no figure en el catálogo: se reintenta solo. Solo se informa de ellos en el bloque "Alta carga de reintentos" si hay acumulación: **más de 3-4 attempts** o **más de 20 jobs/eventos** (por tenant, flujo o error).

### Campo «Escalar»
- Una entrada puede incluir el campo **Escalar**, que indica el equipo al que hay que reportar ese error cuando no es responsabilidad de Products.
- **Si la entrada no lo indica, se entiende que la responsabilidad es del Squad Products** (no hay a quién escalar fuera del squad).
- En el informe, cuando un error conocido tenga un equipo en **Escalar**, indícalo junto al error (equipo, volumen y tenants) y sugiere reportárselo al equipo correspondiente. Esto aplica aunque el impacto sea bajo.
- **Aviso obligatorio al sacar el informe:** si hay KOs achacables a otros squads, avisa al usuario en una sección propia («KOs achacables a otros squads», por equipo, con excepción, tenants, nº, tipo de job/evento e IDs) y sugiérele notificarlo.
- **Cómo se notifica:** como **hilo nuevo** en el canal «Incidencias 🐞» de Pacman en Teams (groupId `1301738f-827e-48ec-8770-3f0922c1c295`, channelId `19:d311bbd5ba844456a3f88ca0f8fcc1ec@thread.tacv2`, tenantId `c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75`; enlace: https://teams.microsoft.com/l/channel/19%3Ad311bbd5ba844456a3f88ca0f8fcc1ec%40thread.tacv2/Incidencias%20%F0%9F%90%9E?groupId=1301738f-827e-48ec-8770-3f0922c1c295&tenantId=c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75). Redacta un borrador, muéstralo y publícalo solo tras confirmación explícita del usuario (cada versión nueva requiere confirmación nueva).

### Reglas de tratamiento
- Los errores conocidos no cuentan como grupos de error. Los de impacto bajo tampoco son hallazgos destacados (salvo la regla anterior).
- Al consultar logs, no excluyas los conocidos con filtros LogQL: consúltalos y agrúpalos igual que el resto, y clasifícalos como conocidos después.
- Si un error conocido cambia claramente (pico de volumen muy superior al habitual o excepción distinta), avísalo como observación.
- **Reejecutar** y **Descartar** de cada entrada fijan qué operaciones de mantenimiento se admiten sobre jobs/eventos con ese error. Si una entrada no admite descartar, no se descarta salvo indicación explícita del usuario, según las reglas del subagente de jobs. Un `504` al reejecutar es esperable (el gateway corta a 30 s): evalúa reconsultando los KO y TO_RETRY, sin repetir la llamada automáticamente.
- Una entrada que dice "acotación estricta" solo aplica dentro de esas condiciones; fuera de ellas, el error se reporta como no conocido.

---

## Impacto alto

### Timeouts de DB2 en `SyncProduct`
- **Impacto:** alto
- **Se reconoce por:**
  - `Db2ConnectionException` / `SqlTimeoutException` (SQLCODE -952) en `SyncProduct`.
  - Agotamiento del pool: `SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after ~60000ms` (cadena `Db2ConnectionException` → `CannotGetJdbcConnectionException` → `ConnectionAcquisitionTimeoutException`).
  - Health check solapado: `DataSource health check failed` si coincide en tenant y franja temporal con los anteriores (ver "Health check de DataSource fallido").
- **Comprobación ampliada:** la query lleva cientos de `LIKE ... OR` sobre `CATENTRY` y tarda en torno a 2 min. Suele darse sobre todo en st y durante la propagación nocturna.
- **Causa:** sobrecarga de DB2 (transitorio). Los timeouts impiden la carga del producto y saturan Legacy.
- **Reejecutar:** sí, en lotes pequeños (1 a pocos IDs); puede no resolverse si DB2 sigue sobrecargado.
- **Descartar:** no.

### Producto corrupto por colores duplicados (`InvalidHierarchyStateException`)
- **Impacto:** alto
- **Se reconoce por:**
  - `InvalidHierarchyStateException` con "Duplicate color code" (p. ej. en `SyncProduct` o `SyncCatalogAttributes`).
  - Error colateral: `InstanceNotFoundException: Color {id} not found for product <productId>` (`ProductHierarchy.getColorWithReferencesOrThrows`, en `SyncProduct`), normalmente antes de que la jerarquía se guarde corrupta.
- **Comprobación ampliada:** anota el producto y la referencia o los colores afectados (p. ej. P:532763033, ref 04803625, colores 551, 552, 709, 715).
- **Causa:** el producto queda corrupto porque tiene colores duplicados dentro de un mismo color (dato persistente).
- **Reejecutar:** no sirve (volverá a fallar).
- **Descartar:** no.
- **Acción sugerida:** recomienda usar el agente **Tech Support** para arreglar el producto.

### `NotAbleToCreateLegacyOutfitException` (impacto condicional)
- **Impacto:** depende de si se cumple la causa de descarte:
  - **bajo:** si el desync Pacman vs Core está VERIFICADO (producto borrado en Core, `STATE_DELETED`, y `deleted=false` en Pacman).
  - **alto:** si no se cumple, no se ha verificado o no se confirma el desync. Si no puedes verificarlo, trátalo como alto e investígalo.
- **Se reconoce por:** jobs `OUTFIT_CREATED` con `NotAbleToCreateLegacyOutfitException`.
- **Comprobación ampliada:** en logs, Legacy `create_bundle_style` devuelve 400 código 23 "Partnumber not found:". Verificación del desync:
  1. Pacman: `POST {products}/v1/catentries` con el `elementId` de la referencia que falla (el de la referencia del log, no necesariamente el del job); debe venir `deleted=false`.
  2. Core: `GetCommercialComponent` (GetCC) sobre ese catentryId; debe venir `state: STATE_DELETED` (colors vacío / ccs eliminados).
- **Causa:** dato desincronizado Pacman vs Core.
- **Reejecutar:** no sirve (fallará siempre mientras persista el desync).
- **Descartar:** solo con el desync VERIFICADO. Sin esa verificación NO se debe proponer descartar. Descartar no corrige el desync ni toca elementos.
- **Acotación:** si no se confirma el desync (p. ej. Core lo tiene vivo o Pacman ya lo tiene `deleted=true`), NO es este caso: considéralo otro error, no propongas descartar e investígalo.

---

## Impacto medio

### `XMediaConcurrentException` (423 LOCKED) en `ExportElementAssets` (tenant zh, productos concretos)
- **Impacto:** medio
- **Se reconoce por:** `XMediaConcurrentException: Concurrent XMedia modification for <productId>` (HTTP 423 LOCKED en el `PUT` a XMedia), en `ExportElementAssets` y su propagación en `JobExecutor` (jobs `ASSETS_CHANGED` y `OPTIMIZED_ASSET_UPDATED`, normalmente en el intento máximo, 50, y marcados como KO), **solo si se cumplen ambas condiciones**:
  - tenant `zh`
  - productId XMedia `475405155` o `475345385`
- **Causa:** estos dos productos fallan siempre y tienen algún problema propio en XMedia (bloqueados). Los reintentos fallan de forma sistemática (dato corrupto).
- **Reejecutar:** no sirve.
- **Descartar:** sí, si se cumplen las dos condiciones anteriores (tenant `zh` y productId `475405155` o `475345385`); en cualquier otro caso no.
- **Acotación estricta:** la misma excepción en otro tenant o con cualquier otro productId es error **no conocido**.
- **Escalar:** Squad de Imagen. `XMediaConcurrentException` es un error al **escribir en XMedia/Assets**, no un problema de Products. Aplica también a los casos que, por la acotación anterior, se tratan como no conocidos.

### `XMediaConnectionException` (error de conexión con XMedia)
- **Impacto:** medio
- **Se reconoce por:** `XMediaConnectionException: Connection exception in XMedia for <id>`, en jobs `ASSETS_CHANGED`, `OPTIMIZED_ASSET_UPDATED` y `OUTFIT_EXPORTED`, normalmente en el intento máximo (50) y marcados como KO. Observado en oy (dataset 203644292, del 27/10 al 29/10/2026).
- **Causa:** fallo de conexión con XMedia al escribir assets, no un problema de Products.
- **Escalar:** Squad de Imagen.
- **Reejecutar:** solo si XMedia está operativo; si persiste el error de conexión, volverán a fallar.
- **Descartar:** no, salvo indicación explícita del usuario.
- **Acotación:** si coincide con una incidencia general de autenticación (401 de Heimdal en el cuerpo), sigue la entrada «Degradación de Heimdal».

### Degradación APICE
- **Impacto:** medio
- **Se reconoce por:**
  - `ApiCeConnectionException` ("Connection error calling APICE"), normalmente por `ResourceAccessException` / `SocketTimeoutException: Read timed out` contra APICE (`apigw-swapi-{tenant}`), p. ej. en `PUT .../products/buyable/set`, pero puede ocurrir con cualquier otro endpoint de APICE. Aparece en `ExportEntityVisibility` y su propagación en `JobExecutor` (jobs `VISIBILITY_PROPAGATE` en KO).
  - `ApiCeVisibilityUnknownException` ("Error writing visibility to Legacy", lanzada en `VisibilityApiceRestDao.resolveHttpServerErrorException`) **solo cuando la causa sea un `502 Bad Gateway`** (`HttpServerErrorException$BadGateway` en `PUT .../products/buyable/set` o `unset`, con cuerpo `_ERR_GENERIC` del backend Legacy).
- **Comprobación ampliada:** el job solo muestra el envoltorio de `ApiCeVisibilityUnknownException`. Para saber si la causa es un 502, lee `full_message` / `Caused by` en los logs del elemento. Indica tenants, volumen y franja temporal.
- **Causa:** APICE no es capaz de asumir la carga que envía Pacman, especialmente durante las propagaciones nocturnas; o carga puntual en un sistema externo al que llama APICE (transitorio).
- **Reejecutar:** sí, es la solución. Conviene que APICE esté ya estable; si siguiera degradado, volverán a fallar.
- **Descartar:** no.
- **Acotación:** `ApiCeVisibilityUnknownException` con cualquier otra causa (otro código HTTP u origen) NO entra aquí: se reporta como error no conocido.

---

## Impacto bajo

### Degradación de Heimdal
- **Impacto:** bajo (por la regla de afectación, se advierte siempre que deje jobs/eventos en KO o TO_RETRY).
- **Se reconoce por:**
  - Timeouts de conexión o lectura (`SocketTimeoutException`, `ConnectTimeoutException`, "Read timed out", "Connect timed out") en `HeimdalUserDetailsRemoteService` (detalle de usuario). Son esporádicos.
  - Fallo de autenticación OAuth2: `ClientAuthorizationException: [invalid_token_response] ... 401 Unauthorized: [no body]`, lanzada por el `OAuth2ClientAuthorizationInterceptor` al pedir el token de cliente. Es la misma causa degradada hasta afectar a todo el servicio.
- **Comprobación ampliada:** el 401 se propaga a `HeimdalUserDetailsRemoteService`, peticiones REST (`SearchProductColorColors`, `GetColorSeasons`, `GetAllTags`), tareas programadas, consumidores Kafka (`MilestonesApi.getCurrentGlobalMilestone`) y llamadas a XMedia (500 con el 401 en el cuerpo). Los jobs afectados son `ASSETS_CHANGED` y `OPTIMIZED_ASSET_UPDATED` en KO con `InternalServerError 500`, normalmente con attempt 0-1. Observado el 2026-10-07 desde ~06:41Z en oy, zh, md y lf, usuario técnico `oauthmpsmartprpro`. Indica si el 401 sigue activo (última línea observada).
- **Causa:** incidencia en Heimdal, servicio externo de autenticación (transitorio).
- **Reejecutar:** sí, una vez resuelta la incidencia de Heimdal. Mientras dure, volverán a fallar. Caso observado: 36 jobs (oy 35, lf 1) reejecutados con éxito.
- **Descartar:** no.
- **Acotación:** un volumen de timeouts claramente superior al habitual se reporta como observación.

### `UnableToExportLiveLegacyException` (reintento programado)
- **Impacto:** bajo, cuando se cumplen las tres condiciones a la vez: tipo `VISIBILITY_PROPAGATE`, error `UnableToExportLiveLegacyException` y `attempt` = 1.
- **Causa:** reintento programado a futuro (no es un fallo real pendiente de atención).
- **Reejecutar:** no hace falta; se reintentará solo.
- **Descartar:** no.
- **Tratamiento:** OMÍTELO del informe de jobs (no lo cuentes ni lo listes en TO_RETRY, KOs ni totales).
- **Acotación estricta:** con `attempt` > 1 o con otro tipo de job NO es este caso y se reporta normalmente.

### Timeouts con otros servicios de terceros
- **Impacto:** bajo
- **Se reconoce por:** timeouts de conexión o lectura contra servicios de terceros. Casos conocidos:
  - **DataGravity:** `Timeout fetching from /v1/datasets/<dataset>/search` (p. ej. dataset `mocaco-novelties-by-mocaco-za`), en `SyncBilledProductColor` y `MaintenanceNewInRestController`. En jobs aparece como `DataGravityTimeoutException` en `FACTU_RETRY` (normalmente KO con attempt 8).
    - **Escalar:** Squad de Tags. `DataGravityTimeoutException` es un error al **cargar las facturaciones**, no un problema de Products.
  - **Amanda:** `SocketTimeoutException: Read timed out` contra `amanda.inditex.com`, p. ej. en `AmandaAssetsDao.fetchContent`.
  - (Heimdal tiene su propia entrada.) Esta lista irá creciendo si se identifican más servicios de terceros.
- **Causa:** timeouts esporádicos de dependencias externas.
- **Acotación:** los timeouts contra DB2 no entran aquí; siguen su propio caso (impacto alto). Un volumen claramente superior al habitual o un servicio de terceros distinto a los listados se reporta como observación o como error no conocido.

### Redespliegue de la aplicación
- **Impacto:** bajo
- **Causa:** los redespliegues (rotación de pods) generan errores colaterales de ciclo de vida. Es ruido esperado. Esta lista irá creciendo a medida que se identifiquen más consecuencias.
- **Se reconoce por (consecuencias conocidas):**
  - `BeanCreationNotAllowedException` ("Singleton bean creation not allowed while singletons of this factory are in destruction") al operar con Kafka durante el apagado, en **cualquier topic/binding** donde Products escribe. Variantes:
    - "Exception thrown while unbinding Binding" (`KafkaMessageChannelBinder`, `SpringApplicationShutdownHook`).
    - "Failed to send ... message" por `BinderException: Exception thrown while building outbound endpoint` causada por `BeanCreationNotAllowedException`, p. ej. `NoveltyMecpbegrPipeProducer` / `PublicationMecpbegrPipeProducer` ("Failed to send MECPBEGR novelty/publication message [V1]", bindings `*Mecpbegr-out-0`) y cualquier otro `*PipeProducer`.
    - Criterio: la causa raíz `BeanCreationNotAllowedException` define el caso, sea cual sea el logger, mensaje o binding.
  - `StatusRuntimeException: UNKNOWN` causada por `RejectedExecutionException: event executor terminated` (Netty) en llamadas gRPC bloqueantes durante el apagado, p. ej. `SyncComingSoon` (`MilestoneRepositoryCommons.findByIdOrThrow` → `getMilestonesByIds`, lanzado desde `ProductCoreEventsExecutor.syncColorAvailability`). Observado en bk el 2026-10-06 ~17:12Z, unos 40 ms antes de los errores de unbinding de Kafka.
  - `ClosedChannelException`, p. ej. `ErrorRestAdapter` con `ClientAbortException`, o `StatusRuntimeException: UNKNOWN: channel closed` en `SyncProduct`.
  - `IllegalStateException: Connection pool shut down` (Apache HttpClient, `Asserts.check`), p. ej. en `AmandaAssetsDao` (`fetchContent`) o `UpdateAssetElementMetadata`.
  - `Socket closed` (`SocketException`), en cualquier componente: p. ej. en `AmandaAssetsDao` al crear el job `image-generate-widths` (`POST /jobs/v2`) o en `SearchProductColorColors`.
  - `IOException` de cliente cortado en `ErrorRestAdapter`: `Connection reset by peer` y `Broken pipe`, al escribir la respuesta durante el redespliegue.
  - `MessageDispatchingException: The application context is not ready to dispatch messages`, p. ej. en `ExportNewIn` (la aplicación aún está arrancando o ya se está apagando).
  - `SQLException: HikariDataSource (HikariPool-1) has been closed` (pool de DB2 cerrado; p. ej. `SyncCatalogAttributes` con "Sync exhausted all 3 attempts for type {X}" vía `Db2ConnectionException` → `CannotGetJdbcConnectionException`).
  - `InterruptedException`, p. ej. "Catalog attribute sync was interrupted before completion" en `SyncCatalogAttributes`. **Excepto** las de `DataSourceHealthIndicator` ("DataSource health check failed"), que van al caso "Health check de DataSource fallido".
  - `IllegalStateException: state should be: open` (cliente Mongo cerrado), p. ej. "Unexpected error occurred in scheduled task" del scheduler de Spring.
  - `MongoInterruptedException: Interrupted waiting for lock`.
- **Comprobación ampliada:** los mensajes no enviados o los eventos no completados se pierden o quedan a medias. Revisa jobs/eventos del tenant en esa franja (p. ej. un Coming Soon desfasado por un `SyncComingSoon` fallido). Si hay afectación, aplica la regla de afectación a jobs/eventos.

### `AvailableOutfitCodeNotFoundException`
- **Impacto:** bajo
- **Se reconoce por:** "No available outfit code found" (`CreateOutfitsFromShootings` / `ShootingMotor`).
- **Causa:** validación legítima: el usuario no puede crear más estilismos de ese tipo.

### `IllegalStateException: Unable to create URL: /contents/<id>`
- **Impacto:** bajo
- **Se reconoce por:** solo cuando ocurre dentro de la importación de content-variants. Criterio principal: la línea contiene `ImportCreativityAssets`. También se reconoce por `LoggingHandler` / `MessageHandlingException`, `FallbackBatchErrorHandler` o topic `*content-variants*`.
- **Causa:** algunos assets tienen la URL mal formada.
- **Acotación estricta:** fuera de la importación de content-variants se reporta como error normal.

### `ValueValidationException` en casos de uso de la New In
- **Impacto:** bajo
- **Causa común:** validaciones de dominio ante acciones ilegítimas del usuario sobre la New In.
- **Se reconoce por:** cualquier `ValueValidationException` lanzada desde un caso de uso relacionado con la New In (p. ej. `MoveNewInElements`, `ChangeProductColorNewInTypes` y, en general, `*NewIn*.execute()`), sea cual sea su mensaje. Firmas ya vistas:
  - **"Specified colors are not in group to change type"** (`ChangeProductColorNewInTypes` / `NewIn.changeColorTypes`): el usuario intenta cambiar el tipo de colores que no pertenecen al grupo indicado. Acción inválida del usuario; validación de dominio legítima.
  - **"Cannot mix different section types in a group"** (`NewInGroup.validateTypeConsistency`): acción inválida del usuario (mezclar secciones de distinto tipo, p. ej. `ADVANCE` y `NEW`, en un mismo grupo). Es una validación de dominio legítima.
  - **"Element not found: <uuid>"** (`NewInElements.lambda$findById$1`): el identificador recibido es un UUID, que no es un ID de elemento válido. Acción ilegal; se desconoce el origen del UUID.
- **Acotación:** `ValueValidationException` en casos de uso que no tengan relación con la New In se reporta como error normal.

### Optimistic locking
- **Impacto:** bajo
- **Se reconoce por:** `OptimisticLockingFailureException` y/o `MongoBulkWriteException` con `E11000 duplicate key error` (índice `_id_`), en cualquier caso de uso relacionado con **shootings o assets en general**. Casos de uso ya vistos:
  - `SaveShootingAssets` (colecciones `*.shootings`)
  - `CalculateShootingAssetState` (colecciones `*.shootings`; p. ej. ráfagas en `lf`)
  - `AllocateElementsAssets` (colección `*.attributes`)
  
  Cada fallo puede generar además una segunda línea ERROR en `org.springframework.integration.handler.LoggingHandler` (consumer Kafka batch-pipe), que forma parte del mismo caso.
- **Causa:** conflicto de concurrencia (optimistic locking) en la escritura de shootings/assets, normalmente en ráfagas por el mismo `_id`.
- **Acotación:** aplica a casos de uso de shootings (`*Shooting*`) y de assets (`*Asset*`, incluida la asignación/reemplazo/cálculo de estado de assets). `OptimisticLockingFailureException` o `MongoBulkWriteException` E11000 en casos de uso **ajenos** a shootings/assets sigue siendo error **no conocido**.

### Health check de DataSource fallido
- **Impacto:** bajo si aparece aislado; alto si se solapa con errores de DB2 (se clasifica entonces dentro de "Timeouts de DB2 en `SyncProduct`").
- **Se reconoce por:** `DataSource health check failed` (logger `org.springframework.boot.actuate.jdbc.DataSourceHealthIndicator`, normalmente WARN), con la cadena `CannotGetJdbcConnectionException` → `SQLException: HikariPool-1 - Interrupted during connection acquisition` → `InterruptedException`.
- **Causa:** el health check del actuator se interrumpe mientras espera una conexión del pool `HikariPool-1`. Suele estar relacionado con la presión sobre DB2.
- **Regla de solapamiento:**
  - Si en el mismo tenant y franja temporal (mismos minutos o ráfaga) aparecen errores de conexión a DB2 (`Db2ConnectionException`, `SqlTimeoutException`/SQLCODE -952, `SQLTransientConnectionException` de HikariPool), clasifica estas líneas **dentro de "Timeouts de DB2", con impacto alto**.
  - Solo si se observan aisladas, sin esos errores de DB2 alrededor, se clasifican aquí con impacto bajo.
  - Indica qué criterio has aplicado y en qué franjas.
- **Acotación:** no es una consecuencia de redespliegue, aunque contenga `InterruptedException`. Clasifícalo aquí aunque coincida con ese criterio del caso de redespliegue.

### `MilestoneNotFoundException` por milestone con formato inválido
- **Impacto:** bajo
- **Se reconoce por:** `MilestoneNotFoundException` (p. ej. "Can't find milestone <valor> inside list: [...]", "Milestone <valor> not found") **solo** cuando el valor recibido no tiene un formato válido de ID de milestone:
  - **Placeholders:** `now`, `next`, `stage` u otros literales parecidos.
  - **Cadena compuesta:** un ID válido seguido de `:` y otro identificador (p. ej. `billCycle-03-09-2026:d0aeadca…`).
- **Comprobación ampliada:** ejemplos observados: `GetElementAssetConfigurations` en za ("Can't find milestone now"), `GetEntitiesVisibilitySnapshots` en md ("Milestone now not found") y `GetNewInTimeline` en oy (`billCycle-03-09-2026:d0aeadca…`).
- **Causa:** el cliente envía un valor que no es un ID de milestone válido. Uso incorrecto de la API, no un fallo del servicio.
- **Acotación estricta:** si el milestone tiene un formato válido (p. ej. `billCycle-21-10-2026` o `night-propagation-06-10-2026`) y aun así no se encuentra, **no** es este caso: error no conocido.

### Peticiones HTTP inválidas (uso incorrecto de la API)
- **Impacto:** bajo
- **Se reconoce por:** `HttpRequestMethodNotSupportedException` (método HTTP no permitido, p. ej. GET sobre un endpoint que no lo admite) `HttpMediaTypeNotSupportedException` (content-type no soportado) y `MissingServletRequestParameterException` (falta un parámetro obligatorio de la petición, p. ej. `attributeTypes`), normalmente en `ErrorRestAdapter`.
- **Causa:** alguien usa una herramienta cliente (p. ej. Postman) de forma incorrecta. No es un fallo del servicio.
- **Acotación:** otras excepciones HTTP de cliente (p. ej. `HttpMessageNotReadableException`, 4xx de negocio) no entran aquí. Un volumen claramente superior al habitual se reporta como observación.
