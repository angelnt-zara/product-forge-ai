# Product Forge: temas pendientes (Teams + Jira)

Comando para escanear los temas pendientes del squad Products (Product Forge): hilos de Teams que mencionan al squad y tickets ITSMECOM abiertos. Opcionalmente, publica el resumen en Teams. Lo ejecuta el agente principal `product-forge-pana`, delegando en el subagente `product-forge-pana-scanner`.

Escanear y publicar son el mismo flujo: la única diferencia es que la publicación añade los pasos de borrador, confirmación y envío.

## Disparadores típicos

- Solo escaneo: "temas pendientes", "hilos sin responder", "escanea los canales", "ITSMECOM", "qué tenemos en Incidencias".
- Con publicación: "publica el resumen", "envíalo a la daily", "mándamelo al chat".

## Parámetros

- **Rango temporal**: por defecto últimos **7 días** sobre la creación del hilo.
- **Canales**: todos por defecto; el usuario puede acotarlos.
- **PRs cerradas**: si incluir hilos con PR cerradas (por defecto no).
- **Publicar**: por defecto **no**. Solo se publica si el usuario lo pide en la petición o lo solicita tras ver el informe.
- **Destino** (solo si publica):
  - **Por defecto:** hilo de la daily en el canal «SQUAD Product Forge 🛠️».
  - **Chat privado del usuario** (`48:notes`), solo si lo pide expresamente.

Los destinos concretos los detalla el subagente.

## Procedimiento

1. **Alcance**: resuelve los parámetros anteriores.
2. **Escaneo**: lanza `product-forge-pana-scanner` en modo **escaneo** con ese alcance. El subagente contiene los canales, los criterios de relevancia, quién cuenta como respuesta del squad, la clasificación (🔴/🟡/🟢/⚪) y la query de ITSMECOM. Si ya hay un escaneo reciente de esta sesión con el mismo alcance, reutilízalo en lugar de repetirlo.
3. **Presentación**: muestra el informe mínimo que devuelva el subagente tal cual (alcance, tabla por canal, pendientes en una línea por hilo, línea de omitidos y limitaciones). Ampliar contexto solo si el usuario lo pide (vuelve a delegar con el hilo/ticket concreto).
4. **Si no se publica**: termina ofreciendo ampliar contexto o publicar el resumen, sin más texto.
5. **Si se publica** (acción que modifica estado):
   1. Pide al subagente el **borrador** en modo **borrador** (formato de publicación, ITSMECOM incluido y validación regex aplicada), pasándole el resultado del escaneo para que no lo repita. El subagente revisa antes el hilo de la daily: si en los últimos 7 días ya se publicó un informe del mismo tipo, omite de «Hilos externos resueltos» los resueltos ya mencionados como tales en él (los temas abiertos se incluyen siempre). Indica al usuario cuántos se han omitido.
   2. Muestra al usuario el borrador tal y como se verá en Teams y el **destino exacto**, y pide confirmación con `question`. Cada versión nueva requiere una confirmación nueva.
   3. Solo con un "sí" claro, delega en el subagente en modo **publicación**, pasándole **el texto exacto confirmado**, el destino y la confirmación del usuario. No permitas que el texto cambie entre borrador y envío.
   4. Informa del resultado. Recuerda que los mensajes enviados no se pueden editar ni borrar.

## Reglas

- Responde siempre en castellano y pásaselo explícitamente al subagente.
- Horas siempre en `Europe/Madrid`, nunca en UTC.
- No inventes hilos, tickets, autores ni fechas: todo sale de lo que devuelva el subagente. Muestra sus limitaciones.
- Si falla la autenticación de Teams/Graph, remite a la skill `teams-setup`.
