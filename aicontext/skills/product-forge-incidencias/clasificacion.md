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

**Canales de soporte de API e implantación (Q - Soporte API Storefront e Imp. Bershka / Lefties / Massimo Dutti / Oysho / Pull and Bear / Stradivarius / Zara Home, todos externos):** en estos canales convive funcionalidad de muchos equipos, así que la relevancia la decide el **filtro reforzado del extractor**: el hilo debe mencionar **Storefront** (o una etiqueta del squad) **y** aportar al menos una **URL de API de Producto** con segmento `/product`, `/products` o `/productsArray` en el path. Los dos requisitos son obligatorios y se evalúan sobre el hilo completo (raíz o respuestas).

Los demás canales externos (B - Gestión incidencias Tecnología, P - Dudas técnicas, PRO Validación Pruebas, Incidencias Entornos Previos) se filtran **solo por mención al squad**, igual que los internos: no les exijas URL de Producto.

- Si el extractor devuelve un hilo que cumple el filtro pero al leerlo el endpoint citado resulta **no ser de Producto** (por ejemplo, `/stores/{id}/menu`, `/tags`, `/grids`, `/checkout`, o una pantalla del frontal de Pacman), **no es del squad**: omítelo como informativo/ajeno y anótalo en una línea.
- Al contrario: si un hilo de estos canales trata claramente un problema de Producto pero el extractor lo dejó en `descartadosPorFiltro` por no encajar en la regla literal (p. ej. la URL viene partida o sin esquema), **no lo rescates por iniciativa propia**: indícalo como limitación y, si es material, pide al extractor que lo recupere con su sesión.
- En estos canales es frecuente que el hilo del rollout de una cadena se abra semanas antes y siga vivo. Clasifícalo por su **última actividad**, no por la fecha del raíz, y ten en cuenta la antigüedad real al valorar criticidad.

## Quién cuenta como «respuesta del squad»

Se considera dada respuesta si **al menos un miembro de ProductForge** ha respondido en el hilo con **una respuesta concreta**.

1. **Respuesta concreta**: aporta información, diagnóstico, solución, decisión, enlace a un Jira/PR, petición de datos específica o indica que ya está corregido/desplegado.
2. **No cuenta**: «lo revisamos», «lo miramos», «ahora lo vemos», «tomo nota», «+1», «👍», «gracias», «cc @alguien» sin contenido, o reacciones. Si el único mensaje del squad es de este tipo, el hilo sigue **pendiente**.
3. Las respuestas de personas ajenas al squad **no** cierran el hilo.

## Hilos iniciados por miembros del squad (peticiones de revisión de PR)

- Si **todas** las PR del hilo están cerradas (`MERGED` o `CLOSED`), el hilo se da por solucionado: **omitir** (motivo «PR cerradas»). El extractor los entrega ya agrupados en `hilosPRCerradas`. Una PR aprobada pero `OPEN` no está cerrada.
- Si alguna PR sigue `OPEN`, el hilo es **interno pendiente**: 🫥 si no hay respuesta concreta, 🏃‍♂️‍➡️ si el squad ya contestó algo concreto y queda una pregunta sin atender. Indica qué PR sigue abierta.
- Sin enlace a PR se clasifica con los criterios normales; los resueltos de miembros del squad se omiten.
- Si el parámetro «PRs cerradas» de la skill está activo, no omitas por este motivo.

## Hilos iniciados por personas externas con PR

No somos responsables del trabajo de squads ajenos: nuestro trabajo termina al revisar el hilo o la PR.

**Regla obligatoria (sin excepciones ni criterio propio):** en un hilo abierto por un externo con **todas** las PR enlazadas aprobadas (`reviewDecision` = `APPROVED` o aprobación explícita de un miembro del squad) el hilo es **✅ resuelto**, aunque la PR siga `OPEN`, sea urgente, el último mensaje sea del squad o haya riesgo de despliegue. Esta regla **prevalece** sobre «en caso de duda, pendiente» y no se plantea al usuario. En el resumen de estado indica «PR aprobada por X, pendiente de merge/despliegue» si procede. Un hilo con PR aprobada pero con una pregunta o petición posterior del solicitante sin atender sigue siendo 🏃‍♂️‍➡️.

Si alguna PR no está aprobada, el hilo sigue pendiente (🫥 o 🏃‍♂️‍➡️ según haya respuesta concreta del squad). Si el estado de la PR no se pudo consultar, pídeselo al extractor.

## Estado de atención (2º emoji)

| Emoji | Estado | Hilos de Teams | ITSMECOM |
|-------|--------|----------------|----------|
| 🫥 | **No atendido** | Ninguna respuesta concreta de un miembro de ProductForge. | Sin asignar o no en progreso (En Cartera). |
| 🏃‍♂️‍➡️ | **Atendido** (en curso) | Hay respuesta concreta del squad pero el hilo sigue abierto (el último mensaje es una nueva pregunta, petición o queja del solicitante sin contestar, o queda trabajo pendiente). | Asignado y En Curso. |
| ✅ | **Resuelto** | Hay respuesta concreta de un miembro de ProductForge y no hay mensajes posteriores sin atender. | Resuelto o cerrado. |

- En caso de duda entre resuelto y pendiente, clasifica como pendiente y déjalo anotado en una línea (salvo la regla de PR aprobada).
- **Informativo vs petición:** un aviso FYI sin petición accionable es **informativo** (⚪, no se cuenta como pendiente). Un aviso con pregunta o petición de apoyo sin responder es una **petición** (🫥). Lee el cuerpo completo antes de marcar informativo.
- Un ticket ITSMECOM cuyos últimos comentarios indican que ya está corregido y solo falta cerrar se mantiene pendiente, se anota en el motivo y no se infla su criticidad.
- Si el ticket de Jira citado en un hilo figura resuelto o cerrado, indícalo.

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
