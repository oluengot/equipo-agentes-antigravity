---
trigger: always_on
description: Al terminar cada tarea, cerrar la respuesta con la tabla de tokens de entrada/salida y su valor en USD y CLP generada por consumo.py.
---

# Resumen de consumo al final de cada tarea

Cuando termines una tarea (cambiaste archivos, ejecutaste comandos o lanzaste subagentes),
cierra tu respuesta final con el resumen de consumo:

1. Corre el script de la skill `equipo` (el que exista):
   - `python .agents/skills/equipo/scripts/consumo.py`
   - `python "$HOME/.gemini/config/skills/equipo/scripts/consumo.py"` (usa `$HOME`, no `~`:
     PowerShell no expande `~` en argumentos de programas)
   Agrega `--modelo-principal <modelo del selector de esta conversación>` si lo sabes
   (`flash`, `pro` o un id como `gemini-3.8-flash`).
   Sin `--desde`, cuenta desde el último mensaje del usuario. Si la tarea empezó antes
   (hubo preguntas y respuestas de por medio), pasa `--desde <hora UTC del pedido original>`.
2. Pega la tabla **tal cual** la imprime el script, bajo el título "Consumo de la tarea".
   No recalcules, no redondees, no inventes cifras: si el script falla, dilo en una línea.

No lo hagas en respuestas puramente conversacionales (preguntas rápidas sin trabajo).
Dentro del flujo `/equipo`, el orquestador ya lo hace en el cierre.
