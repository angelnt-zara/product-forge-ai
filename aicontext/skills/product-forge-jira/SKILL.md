---
name: product-forge-jira
description: Cómo interactuar con Jira (jira.inditex.com) para el squad Product Forge (Pacman Products) mediante el MCP de Jira o, como alternativa, el CLI. Incluye búsqueda con JQL y paginación, lectura de tickets y comentarios, formato de enlaces y reglas para operaciones que modifican estado. Úsala en cualquier flujo que consulte o actualice tickets de Jira.
---

# Product Forge: interacción con Jira

Referencia técnica reutilizable para consultar Jira. No contiene criterios de negocio (qué tickets interesan, qué JQL usar, cómo se presentan en un informe): eso es de cada flujo que la use. Las skills base `jira-pacman` y `jira-cli` aportan el contexto y el CLI; esta skill recoge los detalles técnicos del squad.

## Herramientas

- **Preferente: MCP de Jira.**
  - `jira_search`: búsqueda con JQL.
  - `jira_get_issue`: detalle de un ticket (sin comentarios ni changelog; para los comentarios usa `jira_get_issue_comments`).
- **Alternativa:** si el MCP falla, usa el CLI (skill `jira-cli`) con la misma consulta.
- Si falla la autenticación o la herramienta no está disponible, indícalo como limitación en lugar de inventar datos.

## Búsqueda (`jira_search`)

- Devuelve **10 resultados por página**. Comprueba siempre `total` y pagina con `start_at` hasta cubrirlo; no des por completo un resultado que solo trae la primera página.
- Para repartir resultados por tipo de ticket, lanza la consulta una vez por tipo añadiendo `AND issuetype = <tipo>` (los nombres con espacios van entrecomillados, p. ej. `"Solicitud de servicio"`) en lugar de filtrar a posteriori.
- Las consultas independientes pueden lanzarse en paralelo.

## Lectura de un ticket (`jira_get_issue`)

- **Lee SIEMPRE los comentarios** de cada ticket con `jira_get_issue_comments` (o el CLI), también si `jira_search` ya devuelve la descripción: ni la búsqueda ni `jira_get_issue` traen los comentarios (llegan vacíos). El `changelog` (histórico de estados/asignaciones) tampoco llega con `expand=changelog`: si hace falta, indícalo como limitación. Los **últimos comentarios** reflejan el estado real mejor que la descripción original (causa ya identificada, corrección aplicada, ticket pendiente solo de cierre) y deben condicionar la criticidad y la descripción de cada línea. Si no puedes leerlos, indícalo como limitación.
- Si hay muchos comentarios, pondera los que mencionan a Pacman, Products o Adapter. Sin comentarios, usa la descripción.
- Campos habituales: clave, título (`summary`), tipo, estado, asignado, fecha de creación. No inventes ninguno.
- Fechas en UTC: conviértelas a `Europe/Madrid` al mostrarlas.

## Enlaces

- URL de un ticket: `https://jira.inditex.com/jira/browse/<CLAVE>` (p. ej. `https://jira.inditex.com/jira/browse/ITSMECOM-123`).
- Si el ticket se enlaza dentro de un mensaje de Teams, sigue las reglas de formato de la skill `product-forge-teams` (corchetes en títulos, etc.).

## Operaciones que modifican estado

Crear, comentar, transicionar o asignar tickets **modifica estado**: solo con petición explícita del usuario y tras su confirmación, mostrando exactamente lo que se va a hacer. Por defecto, todo uso de Jira es de solo lectura. Usa para ello las skills `jira-pacman`/`jira-cli`.

### Label del squad al crear tickets

El label del squad Product Forge es siempre `sq#product`. No uses `sq#productforge`, `sq#productForge` ni variantes similares, aunque otras skills (p. ej. `jira-pacman`) lo mencionen para flujos de roadmap.

### Formato de la descripción al crear tickets

Al crear un ticket, estructura la descripción (Jira Wiki Markup) con **paneles**, no con encabezados:

- Cada sección (Contexto, Hipótesis, Objetivo, Criterios de finalización, etc.) va en su propio `{panel:title=Nombre de la sección}...{panel}`.
- **Sin color de fondo**: no uses `bgColor`, `titleBGColor` ni otros parámetros de color; solo `title`.
- No uses encabezados `h1.`–`h6.` para separar secciones.
- Deja una línea en blanco entre paneles.
- Dentro de cada panel puedes usar listas (`*`, `#`), `{{código}}` y enlaces con normalidad.

```text
{panel:title=Contexto}
Texto del contexto.
{panel}

{panel:title=Objetivo}
# Primer objetivo.
# Segundo objetivo.
{panel}
```
