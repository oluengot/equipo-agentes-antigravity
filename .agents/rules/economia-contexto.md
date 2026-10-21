---
trigger: always_on
description: Reglas de gasto mínimo de tokens. Cada token se factura en dinero real (Vertex AI); la entrada nueva no cacheada es el costo principal.
---

# Economía de tokens (se paga en dinero real)

Cada llamada al modelo reenvía todo el contexto de la conversación. Lo caro es la **entrada
nueva** (lo que entra al contexto por primera vez: archivos leídos, salidas de comandos,
páginas web, capturas). Todo lo que metes al contexto se vuelve a pagar en cada llamada siguiente.

## Leer lo justo
- Antes de abrir un archivo, ubica lo que necesitas con `grep_search` / `find_by_name`.
- Archivos de más de ~300 líneas: abre solo el rango que necesitas (StartLine/EndLine).
- No releas un archivo que ya está en el contexto y no cambió.
- Salidas de comandos acotadas: filtra y limita (`| Select-Object -Last 40`, `| tail -40`,
  `--quiet`, `-q`). Nunca vuelques logs, JSON o CSV completos.

## Navegador
- Prefiere leer el texto o el árbol de accesibilidad de la página antes que capturas de pantalla.
- Captura solo cuando necesitas ver algo visual, y a escala reducida si se puede.
- El subagente `browser` se invoca con `Model: flash`, salvo que el usuario pida otro.

## Subagentes
- Siempre con `Model` explícito: `flash` para ejecutar, navegar e investigar; `pro` solo para el `jefe`.
- Encargos cortos y autocontenidos; pide respuestas de pocas líneas y detalles en archivos.

## Conversaciones cortas
- Una conversación por tarea. Al terminar una tarea, no sigas con otra distinta en el mismo hilo:
  sugiere al usuario abrir una conversación nueva (el contexto acumulado se paga en cada llamada).
- Si la conversación ya pasó de ~150 llamadas al modelo, propón cerrar con un resumen en un
  archivo (`.equipo/<slug>/CONTINUAR.md` o similar) y seguir en una conversación nueva desde ese archivo.

## Respuestas
- Respuestas breves. No repitas código o archivos completos en el chat: referencia rutas.
