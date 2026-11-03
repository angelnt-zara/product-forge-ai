---
name: product-forge-sre
description: Cómo consultar logs de Loki mediante el MCP `sre` para Pacman Products (MICPCPRODS) del squad Product Forge. Incluye herramientas disponibles, descubrimiento de labels, selectores del proyecto, estimación de volumen, consultas LogQL y obtención del stack trace íntegro (`full_message`). Úsala en cualquier flujo que consulte logs.
---

# Product Forge: consulta de logs en Loki (MCP `sre`)

Referencia técnica reutilizable para consultar logs. No contiene criterios de análisis (agrupación por firma, recurrencia, clasificación según el catálogo de errores, formato de informe): eso es de cada flujo que la use.

## Herramientas

Servidor MCP `sre`, en particular Loki:
- `sre_loki_label_names`: nombres de labels disponibles.
- `sre_loki_label_values`: valores de un label.
- `sre_loki_index_stats`: estimación de volumen para un selector.
- `sre_loki_query`: consulta LogQL de líneas o métricas.

`observability-analysis` solo sirve como referencia conceptual; no derives a un troubleshooting SRE genérico salvo petición explícita del usuario.

## Reglas de consulta

### 1. Descubrir antes de consultar en grande

No asumas nombres de labels si no están confirmados. Antes de lanzar queries amplias, descubre los labels disponibles para el servicio y valida los valores de los labels clave (`projectkey`/`projectKey`, tenant, level, plataforma si existen). Si un label esperado no aparece, descúbrelo con `sre_loki_label_names`, inspecciona valores con `sre_loki_label_values` y adapta el selector antes de concluir que no hay datos. Labels útiles para acotar: `level`, `tenant`, `platform`, `app`, `namespace` u otros equivalentes.

### 2. Minimizar queries caras

Antes de pedir líneas de log, usa `sre_loki_index_stats` con un selector razonable para estimar el volumen. Si es muy alto, estrecha el selector por nivel de log y por tenant cuando aplique. Para contar o agrupar usa métricas LogQL, no líneas.

### 3. Selector del proyecto

Prueba primero por `projectkey` y, si no devuelve datos, por `projectKey`:
- `{projectkey="MICPCPRODS"}`
- `{projectKey="MICPCPRODS"}`

Si existe label de nivel, limita a `error` o equivalente. Si no, filtra por contenido de línea de la forma más conservadora posible.

### 4. Filtro por tenant

Si el usuario acota por tenant y existe el label, filtra por él. Si no existe pero el dato aparece en la línea, úsalo solo como observación, no como filtro inicial ciego.

### 5. Traza completa en `full_message`

Las líneas de log son JSON, pero en la línea cruda solo se ve `short_message`, con la traza **recortada a un frame por excepción**. Los logs ERROR con excepción tienen además un campo **`full_message`** con el stack trace **íntegro** (todos los frames y las cadenas `Wrapped by:`/`Caused by:`), que NO aparece en la línea cruda: hay que pedirlo explícitamente parseando el JSON.

- **Cuándo:** siempre que haga falta ver el origen real de una excepción (qué clase/método la lanza, qué cliente gRPC o DAO está implicado, qué executor/caso de uso la propaga) o cuando se pida "la traza", "ampliar la traza" o "ver el stack completo". No afirmes que "no existe traza más completa" sin haber probado antes `full_message`.
- **Cómo pedirlo (funciona):** `sre_loki_query` con `| json | keep full_message` y `limit` bajo (1-3). El campo llega en el `stream` de cada resultado como `full_message`:
  `{projectkey="MICPCPRODS", level="ERROR"} |= "TextoDeLaExcepcion" | json | keep full_message`
- **Cómo NO pedirlo:** `| json | line_format "{{.full_message}}"` falla en esta herramienta (error de parseo de la respuesta). Usa `keep`.
- **Coste:** el stack trace es largo; usa ventanas estrechas y `limit` 1-3.
- **Búsqueda por clase:** el logger de eventos es `ProductCoreEventsExecutor` (en plural). Usa el nombre exacto y no limites la búsqueda a nivel ERROR (puede registrarse en WARN).

## Otras notas

- Las horas de Loki vienen en UTC: conviértelas a `Europe/Madrid` al mostrarlas.
- Si no hay datos, indica qué selectores y labels probaste antes de concluir que no hay logs.
