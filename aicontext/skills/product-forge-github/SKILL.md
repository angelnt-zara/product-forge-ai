---
name: product-forge-github
description: Cómo consultar GitHub (repos de inditex) con el CLI `gh` para el squad Product Forge (Pacman Products). Incluye la consulta del estado y las aprobaciones de las PR enlazadas en hilos y la lectura de la lista de miembros del squad desde `team.adoc`. Úsala en cualquier flujo que necesite el estado de una PR o los miembros del squad.
---

# Product Forge: interacción con GitHub

Referencia técnica reutilizable para consultar GitHub en solo lectura. No contiene criterios de negocio (cuándo una PR cuenta como «cerrada» o «resuelta»): eso es de cada flujo que la use.

## Estado de las PR enlazadas

Para cada enlace `https://github.com/inditex/<repo>/pull/<n>` de un hilo:

```bash
gh pr view <n> -R inditex/<repo> --json state,mergedAt,closedAt,title,reviewDecision,reviews
```

- Consulta todas las PR en paralelo (varias llamadas en el mismo bloque), no una a una.
- Interesan `state` (`OPEN`, `MERGED`, `CLOSED`), `mergedAt`/`closedAt`, `title`, `reviewDecision` y las `reviews` con estado `APPROVED` (quién y cuándo).
- Si una PR no es accesible (repo sin permisos, error de `gh`), indícalo como limitación; no supongas su estado.

## Lectura de la lista de miembros del squad

Si no se te pasa ya resuelta:

```bash
gh api repos/inditex/doc-pacman/contents/docs/src/modules/equipo/pages/team.adoc -H "Accept: application/vnd.github.raw"
```

Usa la sección «ProductForge». No uses la etiqueta de Teams.
