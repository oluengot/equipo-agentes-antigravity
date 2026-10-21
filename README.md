# Equipo de agentes para Antigravity

Plantilla reutilizable para cualquier tipo de desarrollo en Google Antigravity (App o CLI) que
reparte el trabajo por costo: el modelo caro **solo planifica**, el barato **ejecuta** y uno
medio **valida**. Usa los subagentes personalizados nativos de Antigravity (`.agents/agents/*.md`)
y una skill (`/equipo`) con el protocolo de orquestación.

## Estructura del equipo

```
Usuario
  └─ ORQUESTADOR  (agente principal · modelo del selector: Gemini 3.8 Flash · Medium)
       ├─ JEFE         model: pro      → planifica: PLAN.md + tarjetas de tarea autocontenidas
       ├─ CONSTRUCTOR  model: flash    → ejecuta 1 tarjeta (varios en paralelo si no comparten archivos)
       └─ SUPERVISOR   model: inherit  → valida cada tarea contra su tarjeta (APROBADO / RECHAZADO)
```

Flujo: triage → jefe planifica → constructores ejecutan → supervisor revisa cada tarea →
si rechaza, el mismo constructor corrige (máx. 2 veces) → si sigue fallando, el jefe
re-planifica solo esa tarea → revisión final del supervisor contra el plan.

## Constructores con enfoque dinámico (dividir en N subagentes)

Los constructores no son un número fijo ni genéricos. `invoke_subagent` recibe por cada
subagente un `TypeName` (qué agente es, lo que fija el modelo) y un `Role` (su especialidad, texto libre):

- `TypeName: constructor` → siempre Flash, barato.
- `Role: "Especialista en tests pytest"`, `"Frontend React + accesibilidad"`… → lo decide el
  jefe (campo **Enfoque** de cada tarjeta) o, fuera de `/equipo`, el propio agente de Antigravity.

El trabajo se reparte en **olas**: todas las tareas de una ola corren a la vez sin compartir
archivos; los archivos comunes (índices, rutas, config) van a una tarea de integración al final.

La regla `delegacion-constructores.md` (siempre activa) hace que esto se cumpla también cuando
**no** usas `/equipo` y simplemente le dices a Antigravity *"divide la tarea en tantos subagentes
como estimes necesario"*: los arma como constructores Flash con el enfoque que él elija,
en vez de clonarse a sí mismo (`self`), que usaría tu modelo caro.

**Importante:** `invoke_subagent` también recibe un campo `Model`. Revisando conversaciones
reales de este PC, Antigravity lanzaba subagentes con `Model: pro` aunque fueran tareas simples.
Por eso el protocolo y la regla exigen `Model: flash` explícito en cada constructor.

## Dónde se va el dinero (diagnóstico 1–21 oct 2026)

Antigravity está conectado al proyecto de Google Cloud `bi-icsa` (Vertex AI, pago por
consumo), así que **cada token se factura**. La consola mostró USD 500,97 netos (USD 844 antes de
USD 343 de ahorros); el SKU más caro es *Gemini 4 Argon Global Text Input* (USD 163).

Los transcripts de este PC (`gasto_mensual.py`) explican como máximo ~USD 271 a precio de
lista; el resto viene de otro lado (otros usuarios o equipos del proyecto, modelos de terceros,
los modelos de fondo de Antigravity). Para verlo: en Facturación → Informes, agrupar por **SKU**
y por la etiqueta **used-by**.

Lo que muestran los transcripts:

1. **La conversación principal es el gasto**: 3 conversaciones de 1.000–1.400 llamadas cada una
   suman ~USD 125 (46 %). Corren con el modelo del selector (Argon High por defecto).
2. **La entrada nueva manda**: 74 M tokens de entrada nueva (USD 149 en Argon) vs. 6,6 M de salida.
   Viene de leer archivos completos, salidas largas de comandos y páginas/capturas del navegador;
   251 llamadas metieron más de 50.000 tokens nuevos de una vez.
3. **Subagentes en `pro` sin necesidad**: un subagente `browser` en `pro` gastó USD 25 solo;
   29 subagentes se lanzaron sin `Model` (heredan el caro).
4. **El 1-dic-2026 Argon duplica su precio**: el mismo uso costaría el doble.

Si todo lo de este PC hubiera corrido en Flash: USD 123 en vez de USD 271 (−55 %), antes de
sumar el ahorro por contexto más chico.

### Qué hace la plantilla para bajarlo

| Palanca | Dónde |
|---|---|
| Conversación principal en Flash (el orquestador no necesita Argon) | App: selector bajo el cuadro de texto, al iniciar cada conversación (con el plan "Agent Platform" no hay predeterminado en Settings). CLI: ya está en `"model": "Gemini 3.8 Flash (Medium)"` en `~/.gemini/antigravity-cli/settings.json` |
| Argon solo para planificar (jefe), una vez por desarrollo | `jefe.md`, skill `equipo` |
| `Model: flash` explícito en todo subagente, incluido `browser` | `delegacion-constructores.md`, `economia-contexto.md` |
| Leer lo justo, salidas acotadas, texto en vez de capturas | `economia-contexto.md` |
| Una conversación por tarea; cortar hilos de más de ~150 llamadas | `economia-contexto.md` |
| Medir cada tarea y cada mes | `consumo.py`, `gasto_mensual.py` |

Configura además una **alerta de presupuesto** en Facturación → Presupuestos y alertas del
proyecto (eso lo hace un administrador de facturación, no los agentes).

## Resumen de consumo (tokens y CLP) al final de cada tarea

`scripts/consumo.py` (dentro de la skill) lee los **transcripts reales** de Antigravity
(`~/.gemini/antigravity/brain/<id>/.system_generated/logs/transcript.jsonl`), donde cada
respuesta del modelo registra `input_tokens`, `cache_read_tokens` y `output_tokens`. Suma la
conversación principal y, de forma recursiva, todos los subagentes que lanzó (los encuentra
por el `conversationId` que devuelve `invoke_subagent`), y lo valoriza así:

- Precio por modelo y por fecha desde `resources/precios.json` (tarifa API Gemini, Standard).
  Ojo: Gemini 4 Argon duplica su precio desde el 1-dic-2026 y Gemini 3.8 Flash desde el
  1-ene-2027; el script aplica el tramo vigente en la fecha de cada llamada.
- Dólar observado del día desde `mindicador.cl` (si no hay conexión, usa `dolar_respaldo_clp`).
- Modelo de cada subagente: su `Model` en la llamada; si no lo trae, el de su tipo
  (`tipos_agente`); `inherit` = el del agente que lo lanzó. El de la conversación principal no
  queda registrado en el transcript: se indica con `--modelo-principal` (por defecto Gemini 3.8 Flash).

Ejemplo real (conversación del 13-oct con 3 subagentes en `pro`):

| Agente | Modelo | Entrada | Entrada en caché | Salida | USD | CLP |
|---|---|---:|---:|---:|---:|---:|
| principal (orquestador) | gemini-4-argon | 1.159.142 | 6.525.313 | 40.242 | 3.3732 | $3.301 |
| browser · Browser Automator | gemini-4-argon | 119.791 | 414.261 | 12.116 | 0.4022 | $394 |
| … | | | | | | |
| **Total** | | **1.481.627** | **7.212.121** | **60.640** | **4.2909** | **$4.199** |

Con `"modalidad": "facturacion"` en `precios.json` (tu caso: proyecto de Google Cloud) es una
estimación de lo que se factura, a precio de lista y antes de descuentos. Con `"cuota"` (planes
Google AI Pro/Ultra) se muestra como costo equivalente. La regla `resumen-consumo.md` hace que
Antigravity lo agregue al final de cada tarea; en `/equipo` queda además en `.equipo/<slug>/CONSUMO.md`.

Uso manual:

```bash
python "$HOME/.gemini/config/skills/equipo/scripts/consumo.py" --modelo-principal flash
```

Opciones: `--desde <ISO>` (por defecto, desde el último mensaje del usuario),
`--conversacion <id>`, `--dolar <valor>`, `--salida <archivo.md>`, `--ahora` (imprime la hora UTC).

## Archivos de intercambio

Todo el intercambio queda en archivos dentro del proyecto, en `.equipo/<slug>/`:
`PEDIDO.md`, `PLAN.md`, `PROGRESO.md`, `tareas/Txx.md`, `reportes/Txx.md`, `revisiones/Txx.md`.
Los agentes se pasan **rutas**, no contenidos; eso es lo que mantiene bajo el gasto de tokens.

## Cómo se asigna cada modelo (importante)

En Antigravity el campo `model` de un subagente **solo acepta tiers**: `inherit`, `flash` o `pro`
(no se puede fijar "Gemini 3.7 Flash Medium" por nombre). Por eso:

| Rol | Cómo obtiene su modelo |
|---|---|
| Jefe | `model: pro` → el tier Pro de tu plan (el mejor razonador) |
| Constructores | `model: flash` → el tier Flash, el más barato |
| Orquestador | Es la conversación principal: **tú eliges el modelo en el selector**. Recomendado: *Gemini 3.8 Flash · Medium* |
| Supervisor | `model: inherit` → hereda el modelo del orquestador, o sea el nivel "medio" que elegiste |

Si quieres un supervisor más estricto, cambia su `model` a `pro`; si quieres abaratarlo más, a `flash`.
Verifica en el panel de subagentes (o `Alt+J` en la CLI) qué modelo corrió cada uno.

## Archivos

| Archivo | Qué es |
|---|---|
| `plantilla/.agents/agents/orquestador.md` | Agente principal (`mainAgent: true`), coordina y no toca código |
| `plantilla/.agents/agents/jefe.md` | Planificador `pro`, solo lectura + escribe en `.equipo/` |
| `plantilla/.agents/agents/constructor.md` | Ejecutor `flash`, solo toca los archivos de su tarjeta |
| `plantilla/.agents/agents/supervisor.md` | Revisor `inherit`, corre git diff y la verificación |
| `plantilla/.agents/skills/equipo/SKILL.md` | Protocolo completo del orquestador (se invoca con `/equipo`) |
| `plantilla/.agents/skills/equipo/scripts/consumo.py` | Suma tokens reales de la tarea (principal + subagentes) y los valoriza en USD y CLP |
| `plantilla/.agents/skills/equipo/resources/precios.json` | Precios por modelo y fecha, mapeo de tiers, dólar de respaldo (editar cuando cambien) |
| `plantilla/.agents/rules/delegacion-constructores.md` | Regla siempre activa: toda división en subagentes usa constructores Flash con `Role` |
| `plantilla/.agents/rules/resumen-consumo.md` | Regla siempre activa: cerrar cada tarea con la tabla de consumo |
| `plantilla/.agents/rules/economia-contexto.md` | Regla siempre activa: leer lo justo, salidas acotadas, subagentes en Flash, conversaciones cortas |
| `gasto_mensual.py` | Diagnóstico del período: top conversaciones, entrada nueva vs caché, subagentes por modelo, escenarios pro/flash |
| `instalar.ps1` | Copia todo a la config global o a un proyecto |

## Instalación

Global (queda disponible en todos tus proyectos):

```bash
powershell -ExecutionPolicy Bypass -File "C:/Users/oluengo/Desarrollos Cloude/Equipo Agentes Antigravity/instalar.ps1"
```

Solo en un proyecto (para versionarlo con el equipo de trabajo):

```bash
powershell -ExecutionPolicy Bypass -File "C:/Users/oluengo/Desarrollos Cloude/Equipo Agentes Antigravity/instalar.ps1" -Proyecto "C:/ruta/al/proyecto"
```

## Uso

1. Abre el proyecto en Antigravity y una conversación nueva.
2. En el selector de modelo elige **Gemini 3.8 Flash · Medium** (ese será el orquestador y el supervisor).
3. Escribe: `/equipo <lo que quieres construir>`
   (o elige `orquestador` como agente principal y escribe el pedido).
4. Sigue el avance en el panel de subagentes y en `.equipo/<slug>/PROGRESO.md`.

## Consejos para que salga barato

- Pedidos chicos: el orquestador hace *triage* y se salta al jefe (1 constructor + supervisor).
- Da contexto en el pedido (stack, cómo se corren los tests): ahorra exploración del jefe.
- Si un tipo de proyecto se repite, agrega una regla o un `AGENTS.md` con las convenciones:
  el jefe planifica mejor y los constructores se equivocan menos.
- Alternativas nativas: `/teamwork-preview` (equipo grande, proyectos de días) y `/boost`
  (bugs difíciles). Son más potentes, pero no te dejan controlar qué modelo usa cada rol.

## Pendiente de verificar en tu Antigravity

- Si un nombre de herramienta en `tools:` no existe, la doc advierte que el subagente puede
  colgarse. Los nombres usados salen de la documentación oficial (hooks); si alguno falla,
  quítalo de la lista.
- Los nombres de argumentos `TypeName` / `Role` / `Workspace` de `invoke_subagent` salen de la
  doc de hooks; confirma en el panel de subagentes que cada constructor muestra su Role y corre en Flash.
- `precios.json` asume `pro` = Gemini 4 Argon y `flash` = Gemini 3.8 Flash. Si en el panel de
  subagentes ves otro modelo, cambia `tiers`.
- No está claro si `output_tokens` del transcript ya incluye los tokens de razonamiento
  (thinking); si no los incluye, el costo real de salida sería algo mayor.
- La ruta `skills: - skills/equipo` del orquestador está escrita como en el ejemplo oficial;
  igual el agente busca la skill `equipo` por nombre.

Fuente: documentación oficial `antigravity.google/docs` (subagents, skills, rules, models), revisada el 2026-10-21.
