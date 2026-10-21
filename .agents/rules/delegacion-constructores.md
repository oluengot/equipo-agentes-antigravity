---
trigger: always_on
description: Toda división de trabajo en subagentes de implementación usa el agente constructor (Flash) con un Role de especialidad, nunca clones del agente principal.
---

# Delegar en subagentes = constructores con enfoque

Cuando dividas trabajo de implementación en subagentes (porque el usuario lo pide, por ejemplo
"divide la tarea en tantos subagentes como estimes necesario", o porque tú lo decides):

1. **Tipo y modelo**: cada subagente se invoca con `invoke_subagent`, `TypeName: constructor`
   y `Model: flash` (explícito: si lo omites puede quedar en `pro`).
   No uses `self` ni `define_subagent` para implementar: heredan el modelo caro de la conversación.
2. **Enfoque**: decide tú la especialidad de cada uno según su parte de la tarea y pásala en
   `Role` (ej. "Especialista en tests", "Frontend React", "Migración SQL"). El modelo sigue siendo Flash.
3. **Cantidad**: tantos como partes independientes tenga el trabajo; si el usuario dio un tope, respétalo.
4. **Sin cruces**: dentro de una misma tanda, dos constructores nunca tocan el mismo archivo.
   Los archivos compartidos (índices, rutas, config, lockfiles) van a una tarea de integración final.
   Lo que depende de otra parte va en una tanda posterior.
5. **Encargo autocontenido** en `Prompt`: objetivo, archivos permitidos, pasos concretos,
   qué no hacer y cómo verificar que terminó. El constructor no ve esta conversación.
6. **Revisión**: al terminar la tanda, revisa los reportes; si el trabajo es delicado, invoca al
   `supervisor` con las tareas y sus reportes antes de dar por cerrado.
7. **Otros subagentes** (`browser`, `research`, tipos propios): también con `Model: flash`
   explícito. `pro` queda reservado para el `jefe` o si el usuario lo pide.

Para desarrollos grandes con plan formal, usa la skill `equipo` (`/equipo`).
