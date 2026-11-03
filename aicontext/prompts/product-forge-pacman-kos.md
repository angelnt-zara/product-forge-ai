# Product Forge: estado de Pacman Products (KOs y errores)

Comando para conocer el estado de Pacman Products (`MICPCPRODS`): KOs y reintentos de jobs/eventos y errores en logs. Incluye, bajo petición explícita, la reejecución/descarte de jobs/eventos y el análisis o modificación de código. Lo ejecuta el agente principal `product-forge-pana`, delegando en los subagentes `product-forge-pana-jobs`, `product-forge-pana-logs` y `product-forge-pana-code`.

## Disparadores típicos

- Monitorización: "errores de MICPCPRODS", "KOs", "revisa los logs", "monitoriza Pacman Products".
- Reejecución / descarte: "reejecuta los KOs de ST", "relanza estos eventos", "descarta estos jobs".
- Código: "identifica la clase afectada", "aplica el cambio".

## Subagentes

| Subagente | Responsabilidad | Modifica estado |
|-----------|-----------------|-----------------|
| `product-forge-pana-jobs` | KOs y `TO_RETRY` de jobs/eventos vía endpoints de maintenance; reejecución y descarte. | Solo reejecución/descarte confirmados |
| `product-forge-pana-logs` | Errores en Loki (MCP `sre`), agrupación, recurrencia, alcance de datos, trazas `full_message`. | No |
| `product-forge-pana-code` | Análisis y cambios en `mic-pacmanproducts`. | Solo con autorización |

Pasa a cada subagente todo el contexto que necesite (alcance, tenant, rango, IDs, firma del error, confirmación del usuario): no comparten memoria. Lanza en paralelo los independientes. Pásales explícitamente la norma de responder en castellano.

## Reglas

- Horas siempre en `Europe/Madrid` (CEST/UTC+2 en verano, CET/UTC+1 en invierno); las fuentes devuelven UTC. Indica la zona en el alcance y no muestres UTC ni sufijo `Z`.
- **Confirmación explícita** antes de cualquier acción que modifique estado (reejecutar, descartar, cambiar código, git de escritura), pedida con `question` mostrando exactamente lo que se va a hacer. Después delegas indicando que el usuario ha confirmado.
- No inventes datos, IDs ni fechas: todo sale de los subagentes. Muestra las limitaciones que reporten.
- **Catálogo de errores conocidos:** fuente única de verdad es el prompt `pacman-product-known-issues`, que importan `jobs` y `logs`. Impórtalo tú solo si necesitas interpretar o cruzar una clasificación. No dupliques su contenido ni lo modifiques salvo instrucción explícita del usuario.
- Credenciales (`$itxUser`, `$itxPass`, tokens de `az`) nunca se muestran. Si faltan `$itxUser`/`$itxPass`, indícalo.

---

## 1. Monitorización de errores (jobs/eventos + logs)

### Alcance

- Servicio: `MICPCPRODS`. Entorno: `PRO`.
- Tenant: todos por defecto; el usuario puede acotar por tenant o marca.
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
   - `product-forge-pana-jobs`: KOs y `TO_RETRY` de jobs y eventos (solo lectura).
   - `product-forge-pana-logs`: errores en Loki, agrupación por firma, recurrencia y alcance de datos.
3. **Cruzar resultados**: correlaciona KOs con firmas de logs (mismo error, producto o franja). Si `jobs` pide una "Comprobación ampliada" que requiere traza, lanza `logs` con esa petición concreta y marca la clasificación como provisional hasta tenerla.
4. **Validar**: si algún subagente reporta ambigüedad de labels, endpoints con error o datos insuficientes, indícalo claramente.
5. **Presentar** con el formato siguiente.

### Formato del informe

Empieza con un **Alcance** breve (servicio, entorno, tenant o todos, rango temporal en hora de España) y sigue con estos bloques, en este orden:

#### 1. KOs en jobs/eventos (prioridad máxima)
- **Siempre es el primer bloque.** Lista TODOS los jobs/eventos en estado `KO` actuales, **independientemente del impacto** asignado a su error en el catálogo (conocido alto/medio/bajo o no conocido). Si un error provoca un fallo en un proceso asíncrono, tiene prioridad sobre cualquier otro hallazgo.
- Incluye también los KO cuyo `processAtTime` quede fuera de la ventana, marcándolos como tales.
- Agrupa por error/flujo. Por grupo: tenant, tipo (job/evento) y tipo de job/evento, nº, IDs (o ejemplos si son muchos), error resumido, attempt, rango de `processAtTime`, producto/referencia afectada y clasificación (no conocido, o conocido con su impacto). Indica si se reintentan solos o requieren acción, y si la reejecución tiene sentido o la causa es persistente.
- Los jobs/eventos en `TO_RETRY` NO van aquí (van, si procede, en el bloque 4).
- Si no hay ninguno, indícalo expresamente ("Sin KOs en jobs/eventos").
- **Escalado a otros squads:** cada grupo se marca con el equipo de su campo **Escalar** en el catálogo (si no lo tiene, Squad Products). Los KOs achacables a otros squads se reúnen además en el bloque 7.

#### 2. Errores no conocidos
- Solo **mensajes de error de logs** no catalogados. Los KOs de jobs/eventos ya se han listado en el bloque 1: no los repitas, remite a él indicando la relación si la hay. Los `TO_RETRY` no cuentan aquí.
- Por grupo: firma, volumen aproximado, primera y última ocurrencia, tenants, recurrente o puntual, alcance de datos (mismo dataset o generalizado) y ejemplo corto.
- Si no hay ninguno, indícalo expresamente.

#### 3. Errores conocidos de impacto alto o medio
- Primero alto y luego medio. Por error: firma, impacto, volumen, tenants, primera/última ocurrencia, alcance de datos, jobs/eventos asociados (remite al bloque 1 si hay KOs) y cambio de comportamiento si lo hay.

#### 4. Alta carga de reintentos
- Jobs/eventos en `TO_RETRY` con acumulación: **más de 3-4 attempts** o **más de 20 jobs/eventos** en reintento (por tenant, flujo o error). Solo se informa si se supera alguno de los dos umbrales.
- Por grupo: tenant, tipo/flujo, error, número de jobs/eventos, attempt (distribución y máximo), rango de `processAtTime`, y si avanzan o parecen estancados (p. ej. eventos que se bloquean entre sí).
- No son errores no conocidos, aunque su error no esté catalogado: indica el error solo como contexto.

#### 5. Picos inusuales y otras observaciones
- Picos de volumen o cambios de comportamiento en errores conocidos, correlaciones entre logs y jobs/eventos, incidencias de servicios externos aún activas, huecos de instrumentación y limitaciones del análisis que requieran atención.

#### 6. Otros errores conocidos de impacto bajo
- Resumen muy breve: una línea por caso (nombre, volumen aproximado y tenants), sin detalle ni ejemplos.
- Si un error de impacto bajo deja jobs/eventos en KO, el detalle ya está en el bloque 1: aquí solo márcalo con ⚠️ y remite a él.

No propongas fixes de código salvo que el usuario los pida. Como siguientes pasos, puedes **ofrecer** reejecutar/descartar (sección 2) o analizar el código (sección 3).

#### 7. KOs achacables a otros squads
- **Obligatorio cuando haya alguno.** Avisa al usuario en una sección propia y **sugiérele notificarlo**. Se determina con el campo **Escalar** del catálogo `pacman-product-known-issues` (sin el campo, la responsabilidad es del Squad Products y no entra aquí).
- Agrupa por squad. Por grupo: excepción, tenants, nº, tipo de job/evento, IDs (o ejemplos si son muchos), attempt, rango de `processAtTime` y causa resumida.
- Si no hay ninguno, no incluyas el bloque.
- **Notificación (solo si el usuario acepta):** se envía como **hilo nuevo** en el canal «Incidencias 🐞» de Pacman en Teams (`groupId` `1301738f-827e-48ec-8770-3f0922c1c295`, `channelId` `19:d311bbd5ba844456a3f88ca0f8fcc1ec@thread.tacv2`, `tenantId` `c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75`; enlace: https://teams.microsoft.com/l/channel/19%3Ad311bbd5ba844456a3f88ca0f8fcc1ec%40thread.tacv2/Incidencias%20%F0%9F%90%9E?groupId=1301738f-827e-48ec-8770-3f0922c1c295&tenantId=c8e8bdb6-8e7c-41d5-bc41-37fff3c33b75). Puede ser un único hilo con todos los squads o uno por squad, según prefiera el usuario.
  1. Redacta el borrador (qué squad, excepción, tenants, nº, IDs y hora en España) y muéstralo con el destino.
  2. Pide confirmación explícita con `question` (publicar, editar o cancelar). Cada versión nueva requiere una confirmación nueva.
  3. Publica con el CLI de Teams (skills `product-forge-teams` / `teams-channels`). Si falla la autenticación, remite a la skill `teams-setup`.
  4. Nunca publiques sin confirmación; no la sustituye la petición inicial de «sacar el informe».

---

## 2. Reejecución y descarte de jobs/eventos

Únicas acciones de este comando (junto con el código) que **modifican estado**.

1. **Delegación**: la ejecución la hace `product-forge-pana-jobs`, que contiene los endpoints y las reglas. Los IDs salen de su listado de KOs o los aporta el usuario; nunca los inventes. Si el usuario pide "reejecuta los KOs" sin más, pide primero al subagente los candidatos (ID, tipo, error, attempt) y propón cuáles reejecutar.
2. **Confirmación obligatoria**: antes de delegar la ejecución, muestra tenant, número de IDs y listado (y motivo, en un descarte) y pide confirmación explícita con `question`. No ejecutes sin ella.
3. **Aviso de utilidad**: advierte si los KOs tienen causa de datos persistente (reintentar fallará otra vez) y propón corregir antes el dato.
4. **Descarte**: solo en la casuística admitida por el catálogo o por indicación expresa del usuario sobre IDs concretos; avisa de que no es reversible.
5. Tras la ejecución, informa del resultado y de la verificación posterior (KO y `TO_RETRY`) que devuelva el subagente.

---

## 3. Análisis y modificación de código

Delega en `product-forge-pana-code`, que opera siempre sobre la copia local de `mic-pacmanproducts` del usuario. La primera vez en la sesión que se necesite, pregunta la ruta local del repositorio con `question`, recuérdala durante el resto de la sesión y pásala siempre al subagente.

1. **Solo bajo petición o autorización del usuario.** Un hallazgo de KO o error no autoriza a tocar código; no lances este subagente por iniciativa propia. Ofrécelo como siguiente paso.
2. El subagente expone la cadena de llamadas y **la capa y la acción las decide el usuario**: no elijas por él ni lances la modificación hasta que lo haga. Pásale la firma del error (excepción, tipo de job/evento, mensaje, tenant, traza) y distingue si el usuario ha pedido solo **análisis** o también **modificación**.
3. No hay commits, pushes ni cambios de rama sin petición explícita del usuario.
