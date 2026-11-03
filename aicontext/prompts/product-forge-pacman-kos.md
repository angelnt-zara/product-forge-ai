# Product Forge: estado de Pacman Products (KOs y errores)

Comando para conocer el estado de Pacman Products (`MICPCPRODS`): KOs y reintentos de jobs/eventos y errores en logs. Incluye, bajo petición explícita, la reejecución/descarte de jobs/eventos y el análisis o modificación de código. Lo ejecuta el agente principal `product-forge-pana`, delegando en los subagentes `product-forge-kos-jobs`, `product-forge-kos-logs` y `product-forge-kos-code`.

## Disparadores típicos

- Monitorización: "errores de MICPCPRODS", "KOs", "revisa los logs", "monitoriza Pacman Products".
- Reejecución / descarte: "reejecuta los KOs de ST", "relanza estos eventos", "descarta estos jobs".
- Código: "identifica la clase afectada", "aplica el cambio".

## Subagentes

| Subagente | Responsabilidad | Modifica estado |
|-----------|-----------------|-----------------|
| `product-forge-kos-jobs` | KOs y `TO_RETRY` de jobs/eventos vía endpoints de maintenance; reejecución y descarte. | Solo reejecución/descarte confirmados |
| `product-forge-kos-logs` | Errores en Loki (MCP `sre`), agrupación, recurrencia, alcance de datos, trazas `full_message`. | No |
| `product-forge-kos-code` | Análisis y cambios en `mic-pacmanproducts`. | Solo con autorización |

Pasa a cada subagente todo el contexto que necesite (alcance, tenant, rango, IDs, firma del error, confirmación del usuario): no comparten memoria. Lanza en paralelo los independientes.

## Reglas

- **Catálogo de errores:** fuente única de verdad es el prompt `product-forge-pacman-kos-catalog`, que importan `jobs` y `logs`. Impórtalo tú solo si necesitas interpretar o cruzar una clasificación. No dupliques su contenido ni lo modifiques salvo instrucción explícita del usuario.

---

## 1. Monitorización de errores (jobs/eventos + logs)

### Alcance

- Servicio: `MICPCPRODS`. Entorno: `PRO`.
- Tenant: todos por defecto (los 8 de la tabla); el usuario puede acotar por tenant o marca. Es la **única tabla de tenants**: al delegar, pasa a los subagentes los códigos de tenant del alcance resuelto, ya que ellos no la tienen.
- Rango: últimas `24h` por defecto.

| Tenant | Marca |
|--------|-------|
| `za` | Zara |
| `zh` | Zara Home |
| `pb` | Pull&Bear |
| `st` | Stradivarius |
| `bk` | Bershka |
| `md` | Massimo Dutti |
| `oy` | Oysho |
| `lf` | Lefties |

### Procedimiento

1. **Resolver alcance** (servicio, entorno, tenant, rango).
2. **Delegar en paralelo**:
   - `product-forge-kos-jobs`: KOs y `TO_RETRY` de jobs y eventos (solo lectura).
   - `product-forge-kos-logs`: errores en Loki, agrupación por firma, recurrencia y alcance de datos.
3. **Cruzar resultados**: correlaciona KOs con firmas de logs (mismo error, producto o franja). Si `jobs` pide una "Comprobación ampliada" que requiere traza, lanza `logs` con esa petición concreta y marca la clasificación como provisional hasta tenerla.
4. **Validar**: si algún subagente reporta ambigüedad de labels, endpoints con error o datos insuficientes, indícalo claramente.
5. **Componer y presentar** el informe tú, con el formato siguiente. Los subagentes solo exponen la información relevante (grupos de error, volúmenes, tenants, ventanas, alcance de datos, limitaciones): la estructura, el orden de prioridad y los criterios de presentación son los de este comando.

### Formato del informe

El informe lo compones **tú** con lo que exponen `product-forge-kos-jobs` y `product-forge-kos-logs`; ellos no deciden estructura, orden ni prioridades. Síguelo al pie de la letra.

#### Criterios generales

- **Orden de prioridad (obligatorio):** primero los KOs en jobs/eventos; después los errores NO catalogados; después los catalogados de impacto alto y medio; al final los de impacto bajo como lista muy breve. Dedica el detalle y la extensión en ese mismo orden.
- **Prioridad de los KOs:** si un error provoca un fallo en un proceso asíncrono (KO), tiene prioridad sobre cualquier otro hallazgo, **independientemente del impacto** asignado a su error en el catálogo.
- **Ordena dentro de cada bloque** de más a menos relevante: recurrentes y recientes primero. En alto/medio, primero alto y después medio.
- **Bloque vacío:** si no hay hallazgos en un bloque, indícalo expresamente donde se pide («Sin KOs en jobs/eventos», «Sin errores no catalogados») y omite el resto de bloques vacíos.
- **Cifras siempre:** indica siempre la cifra de KO y de TO_RETRY, aunque sea 0.
- **Antiguo vs reciente:** si no hay rango del usuario, muestra todo lo devuelto pero destaca lo de las últimas 24 h; indica si un grupo es histórico acumulado o reciente.
- **Sin reintentos:** marca explícitamente los KO con `attempt` = 1 (no se reintentaron: pueden requerir revisión manual).
- **Catálogo:** aplica las entradas tal cual (impacto, firma, comprobación ampliada, **Reejecutar**, **Descartar**, **Escalar**). Respeta las instrucciones de omisión de una entrada (p. ej. `UnableToExportLiveLegacyException` con `attempt` = 1 se omite del informe de jobs). En entradas de impacto condicional, aplica el impacto según la condición; si no se puede verificar, trátalo como el más alto. Si falta una comprobación ampliada, deja la clasificación como provisional.
- **Impacto bajo con afectación a jobs/eventos:** un error de impacto bajo que deja jobs/eventos en KO o TO_RETRY no se oculta: se advierte con ⚠️ según la «Regla de afectación a jobs/eventos» del catálogo.
- **Estilo:** síntesis e interpretación; sin JSON crudo, sin ruido de exploración ni listados enormes de líneas de log ni de IDs (ejemplos si son muchos).

#### Estructura

Empieza con **Alcance** y un **Resumen**, y sigue con los bloques 1 a 7 en este orden.

**Alcance** (breve, en hora de España): servicio, entorno, tenant o todos, rango temporal (por `processAtTime` en jobs), tenants consultados y resultado de cada consulta (OK / vacío / error), selector o estrategia de logs a alto nivel y **totales de KO y de TO_RETRY, en jobs y en eventos, por tenant**.

**Resumen:** nº de KOs en jobs/eventos; nº de grupos de error NO catalogados y cuáles son recurrentes o puntuales; si hay catalogados de impacto medio/alto activos; e indicio global (localizado, generalizado o mixto).

#### 1. KOs en jobs/eventos (prioridad máxima)
- **Siempre es el primer bloque.** Lista TODOS los jobs/eventos en estado `KO` actuales, **independientemente del impacto** de su error en el catálogo (catalogado alto/medio/bajo o no catalogado).
- Incluye también los KO cuyo `processAtTime` quede fuera de la ventana, marcándolos como tales.
- Mantén separados jobs y eventos. Agrupa por firma de error/flujo. Por grupo: tenant, tipo (job/evento) y tipo de job/evento, nº, IDs (o ejemplos si son muchos), error resumido, distribución de `attempt`, primer y último `processAtTime`, producto/referencia afectada, alcance de datos (mismo conjunto, generalizado o indeterminado), recurrente o puntual, ejemplo corto y clasificación (no catalogado, o catalogado con su impacto). Indica si se reintentan solos o requieren acción, y si la reejecución tiene sentido o la causa es persistente (según **Reejecutar** del catálogo). Si el grupo tiene candidatos a reejecución, lístalos (ID, tipo, error, attempt).
- Si hay productos que aparecen en más de un KO (jobs y/o eventos), indícalos aquí con tenant, flujos y nº de KOs.
- Los jobs/eventos en `TO_RETRY` NO van aquí (van, si procede, en el bloque 4).
- Si no hay ninguno, indícalo expresamente ("Sin KOs en jobs/eventos").
- **Escalado a otros squads:** cada grupo se marca con el equipo de su campo **Escalar** en el catálogo (si no lo tiene, Squad Products). Los KOs achacables a otros squads se reúnen además en el bloque 7.

#### 2. Errores no catalogados
- Solo **mensajes de error de logs** no catalogados. Los KOs de jobs/eventos ya se han listado en el bloque 1: no los repitas, remite a él indicando la relación si la hay. Los `TO_RETRY` no cuentan aquí.
- Ordénalos de más a menos relevante (recurrentes y recientes primero). Por grupo: firma, volumen aproximado, primera y última ocurrencia observada, tenants, recurrente o puntual, alcance de datos (mismo dataset, generalizado o indeterminado) y ejemplo representativo corto.
- Si no hay ninguno, indícalo expresamente.

#### 3. Errores catalogados de impacto alto o medio
- Primero alto y luego medio. Por error: firma, impacto, volumen aproximado, tenants, primera/última ocurrencia, alcance de datos, jobs/eventos asociados (remite al bloque 1 si hay KOs), cambio de comportamiento si lo hay y la acción sugerida cuando la tenga (p. ej. Tech Support).
- Si no hay ninguno, indícalo expresamente.

#### 4. Alta carga de reintentos
- Jobs/eventos en `TO_RETRY` con acumulación: **más de 3-4 attempts** o **más de 20 jobs/eventos** en reintento (por tenant, flujo o error). Solo se informa si se supera alguno de los dos umbrales.
- Por grupo: tenant, tipo/flujo, error (como contexto), nº, distribución de `attempt` y máximo, rango de `processAtTime`, y si avanzan o parecen estancados (p. ej. eventos que se esperan o bloquean entre sí).
- No son errores no catalogados, aunque su error no esté catalogado: indica el error solo como contexto.

#### 5. Picos inusuales y otras observaciones
- Picos de volumen o cambios de comportamiento en errores catalogados, correlaciones entre logs y jobs/eventos (mismo error, producto o franja), incidencias de servicios externos aún activas, huecos de instrumentación, comprobaciones ampliadas pendientes y limitaciones del análisis (labels ambiguos, logs poco estructurados, muestreo incompleto, endpoints con error, campos ausentes, respuestas truncadas) que requieran atención.

#### 6. Otros errores catalogados de impacto bajo
- Lista muy breve: una línea por caso (nombre, volumen aproximado y tenants), sin detalle, ejemplos ni franjas horarias.
- Si un error de impacto bajo deja jobs/eventos en KO, el detalle ya está en el bloque 1: aquí solo márcalo con ⚠️ y remite a él, con tenant, nº, attempt y si se reintentan solos.

No propongas fixes de código salvo que el usuario los pida. Como siguientes pasos, puedes **ofrecer** reejecutar/descartar o analizar el código.

#### 7. KOs achacables a otros squads
- **Obligatorio cuando haya alguno.** Avisa al usuario en una sección propia y **sugiérele notificarlo**. Se determina con el campo **Escalar** del catálogo `product-forge-pacman-kos-catalog` (sin el campo, la responsabilidad es del Squad Products y no entra aquí).
- Agrupa por squad. Por grupo: excepción, tenants, nº, tipo de job/evento, IDs (o ejemplos si son muchos), attempt, rango de `processAtTime` y causa resumida.
- Si no hay ninguno, no incluyas el bloque.
- **Canal de escalado:** el escalado se publica como **hilo nuevo** (con título, según las reglas de `product-forge-teams`). **Sugiere** el canal según el tipo de problema, explica brevemente por qué y deja que el usuario elija:

  | Tipo de problema | Canal | `groupId` / `channelId` | Enlace |
  |------------------|-------|-------------------------|--------|
  | Problemas internos en Pacman (por defecto: KOs achacables a otros squads de Pacman) | «Incidencias 🐞» | `1301738f-827e-48ec-8770-3f0922c1c295` / `19:d311bbd5ba844456a3f88ca0f8fcc1ec@thread.tacv2` | https://teams.microsoft.com/l/channel/19%3Ad311bbd5ba844456a3f88ca0f8fcc1ec%40thread.tacv2/Incidencias%20%F0%9F%90%9E?groupId=1301738f-827e-48ec-8770-3f0922c1c295&tenantId=c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75 |
  | Problemas con Product Core | «SQUAD Product Lifecycle» | `2dc145f7-b281-4896-bdec-c65d2e465b6d` / `19:52e629a2da9145a8a1660bf944310236@thread.skype` | https://teams.microsoft.com/l/channel/19%3A52e629a2da9145a8a1660bf944310236%40thread.skype/SQUAD%20Product%20Lifecycle?groupId=2dc145f7-b281-4896-bdec-c65d2e465b6d&tenantId=c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75 |
  | Problemas críticos | «B - Gestión incidencias Tecnología» | `fc58da2f-67b0-49ab-a3df-d2b84d676f26` / `19:38382f0598414c04b7a4354ea823f795@thread.tacv2` | https://teams.microsoft.com/l/channel/19%3A38382f0598414c04b7a4354ea823f795%40thread.tacv2/B%20-%20Gesti%C3%B3n%20incidencias%20Tecnolog%C3%ADa?groupId=fc58da2f-67b0-49ab-a3df-d2b84d676f26&tenantId=c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75 |

  `tenantId` de todos: `c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75`.
- **Notificación (solo si el usuario acepta):** puede ser un único hilo con todos los squads o uno por squad, según prefiera el usuario. **Pide siempre confirmación** del canal y del texto exacto.
  1. Redacta el borrador (qué squad, excepción, tenants, nº, IDs y hora en España) y muéstralo con el canal sugerido.
  2. Pide confirmación explícita con `question` (publicar, editar o cancelar). Cada versión nueva requiere una confirmación nueva.
  3. Publica el hilo nuevo con el CLI de Teams (skill `teams-channels`).
  4. Nunca publiques sin confirmación; no la sustituye la petición inicial de «sacar el informe».

---

## 2. Reejecución y descarte de jobs/eventos

Únicas acciones de este comando (junto con el código) que **modifican estado**.

1. **Delegación**: la ejecución la hace `product-forge-kos-jobs`, que contiene los endpoints y las reglas. Los IDs salen de su listado de KOs o los aporta el usuario; nunca los inventes. Si el usuario pide "reejecuta los KOs" sin más, pide primero al subagente los candidatos (ID, tipo, error, attempt) y propón cuáles reejecutar.
2. **Confirmación obligatoria**: antes de delegar la ejecución, muestra tenant, número de IDs y listado (y motivo, en un descarte) y pide confirmación explícita con `question`. No ejecutes sin ella.
3. **Aviso de utilidad**: advierte si los KOs tienen causa de datos persistente (reintentar fallará otra vez) y propón corregir antes el dato.
4. **Descarte**: solo en la casuística admitida por el catálogo o por indicación expresa del usuario sobre IDs concretos; avisa de que no es reversible.
5. Tras la ejecución, informa del resultado y de la verificación posterior (KO y `TO_RETRY`) que devuelva el subagente.

---

## 3. Análisis y modificación de código

Delega en `product-forge-kos-code`, que opera siempre sobre la copia local de `mic-pacmanproducts` del usuario. La primera vez en la sesión que se necesite, pregunta la ruta local del repositorio con `question`, recuérdala durante el resto de la sesión y pásala siempre al subagente.

1. **Solo bajo petición o autorización del usuario.** Un hallazgo de KO o error no autoriza a tocar código; no lances este subagente por iniciativa propia. Ofrécelo como siguiente paso.
2. El subagente expone la cadena de llamadas y **la capa y la acción las decide el usuario**: no elijas por él ni lances la modificación hasta que lo haga. Pásale la firma del error (excepción, tipo de job/evento, mensaje, tenant, traza) y distingue si el usuario ha pedido solo **análisis** o también **modificación**.
3. No hay commits, pushes ni cambios de rama sin petición explícita del usuario.
