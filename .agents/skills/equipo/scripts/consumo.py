"""Resumen de tokens y costo (USD y CLP) de una tarea en Antigravity.

Lee los transcripts reales de Antigravity
(~/.gemini/antigravity/brain/<id>/.system_generated/logs/transcript.jsonl),
suma los tokens de la conversación principal y de todos los subagentes que lanzó
(recursivo), y los valoriza con los precios de ../resources/precios.json y el
dólar observado del día (mindicador.cl).

Uso:
  python consumo.py --ahora                         # imprime la hora UTC (para marcar el inicio)
  python consumo.py                                 # tarea actual: desde el último mensaje del usuario
  python consumo.py --desde 2026-10-21T13:05:00Z    # desde una marca de inicio
  python consumo.py --modelo-principal pro --salida .equipo/x/CONSUMO.md
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def fecha(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def leer(ruta):
    filas = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if linea.strip():
                try:
                    filas.append(json.loads(linea))
                except json.JSONDecodeError:
                    pass
    return filas


def ruta_transcript(app_dir, cid):
    return app_dir / "brain" / cid / ".system_generated" / "logs" / "transcript.jsonl"


def hijos(filas):
    """Subagentes lanzados en una conversación: [(conversationId, spec)]."""
    out, pendientes = [], []
    for fila in filas:
        for tc in fila.get("tool_calls") or []:
            if tc.get("name") == "invoke_subagent":
                specs = (tc.get("args") or {}).get("Subagents") or []
                if isinstance(specs, str):
                    try:
                        specs = json.loads(specs)
                    except json.JSONDecodeError:
                        specs = []
                pendientes.extend(specs if isinstance(specs, list) else [])
        contenido = fila.get("content")
        if isinstance(contenido, str) and "Created the following subagents" in contenido:
            ids = re.findall(r'"conversationId"\s*:\s*"(' + UUID + ')"', contenido)
            for cid in ids:
                out.append((cid, pendientes.pop(0) if pendientes else {}))
            pendientes = []
    return out


def resolver_modelo(valor, padre, cfg):
    if not valor or valor == "inherit":
        return padre
    return cfg["tiers"].get(valor, valor)


def modelo_de_spec(spec, padre, cfg):
    m = spec.get("Model")
    if not m:
        m = cfg["tipos_agente"].get(spec.get("TypeName", ""), "inherit")
    return resolver_modelo(m, padre, cfg)


def precio(cfg, modelo, cuando):
    tramos = cfg["modelos"].get(modelo)
    if not tramos:
        return None
    dia = cuando.date().isoformat() if cuando else datetime.now(timezone.utc).date().isoformat()
    vigente = None
    for t in sorted(tramos, key=lambda t: t["desde"]):
        if t["desde"] <= dia:
            vigente = t
    return vigente


def dolar(cfg, forzado):
    if forzado:
        return forzado, "indicado a mano"
    try:
        with urllib.request.urlopen("https://mindicador.cl/api/dolar", timeout=8) as r:
            serie = json.load(r)["serie"][0]
            return float(serie["valor"]), f"dólar observado {serie['fecha'][:10]} (mindicador.cl)"
    except Exception:
        return float(cfg["dolar_respaldo_clp"]), "valor de respaldo de precios.json (sin conexión)"


def conversacion_actual(app_dir):
    """El transcript top-level modificado más recientemente (no es hijo de otro)."""
    recientes = sorted((app_dir / "brain").glob("*/.system_generated/logs/transcript.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:15]
    ids = [p.parents[2].name for p in recientes]
    hijos_de_recientes = set()
    for p in recientes:
        hijos_de_recientes.update(cid for cid, _ in hijos(leer(p)))
    for cid in ids:
        if cid not in hijos_de_recientes:
            return cid
    return ids[0] if ids else None


def clp(v):
    txt = f"{v:,.0f}" if v >= 10 else f"{v:,.1f}"
    return "$" + txt.replace(",", "X").replace(".", ",").replace("X", ".")


def num(n):
    return f"{n:,}".replace(",", ".")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ahora", action="store_true", help="imprime la hora UTC actual y sale")
    ap.add_argument("--conversacion", help="conversationId principal (por defecto, la activa)")
    ap.add_argument("--desde", help="marca ISO de inicio de la tarea (por defecto, último mensaje del usuario)")
    ap.add_argument("--modelo-principal", help="modelo del selector de la conversación principal (pro, flash o id)")
    ap.add_argument("--app-dir", default=str(Path.home() / ".gemini" / "antigravity"))
    ap.add_argument("--precios", default=str(AQUI.parent / "resources" / "precios.json"))
    ap.add_argument("--dolar", type=float, help="forzar valor del dólar en CLP")
    ap.add_argument("--salida", help="además de imprimir, guardar el resumen en este archivo .md")
    a = ap.parse_args()

    if a.ahora:
        print(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        return

    cfg = json.loads(Path(a.precios).read_text(encoding="utf-8"))
    app_dir = Path(a.app_dir).expanduser()
    principal = a.conversacion or conversacion_actual(app_dir)
    if not principal or not ruta_transcript(app_dir, principal).exists():
        sys.exit(f"No encontré el transcript de la conversación en {app_dir / 'brain'}")

    filas_p = leer(ruta_transcript(app_dir, principal))
    desde = fecha(a.desde) if a.desde else None
    if not desde:
        entradas = [f for f in filas_p if f.get("type") == "USER_INPUT" and f.get("created_at")]
        desde = fecha(entradas[-1]["created_at"]) if entradas else None

    modelo_p = resolver_modelo(a.modelo_principal or cfg["modelo_principal"], cfg["modelo_principal"], cfg)

    agentes, cola, vistos = [], [(principal, "principal (orquestador)", modelo_p, filas_p)], set()
    while cola:
        cid, etiqueta, modelo, filas = cola.pop(0)
        if cid in vistos:
            continue
        vistos.add(cid)
        if filas is None:
            ruta = ruta_transcript(app_dir, cid)
            if not ruta.exists():
                continue
            filas = leer(ruta)
        tot = {"llamadas": 0, "entrada": 0, "cache": 0, "salida": 0, "usd": 0.0, "sin_precio": False}
        for f in filas:
            if "input_tokens" not in f:
                continue
            cuando = fecha(f.get("created_at"))
            if desde and cuando and cuando < desde:
                continue
            ent, cac, sal = f.get("input_tokens", 0), f.get("cache_read_tokens", 0), f.get("output_tokens", 0)
            tot["llamadas"] += 1
            tot["entrada"] += ent
            tot["cache"] += cac
            tot["salida"] += sal
            p = precio(cfg, modelo, cuando)
            if p:
                tot["usd"] += (ent * p["entrada"] + cac * p["cache"] + sal * p["salida"]) / 1_000_000
            else:
                tot["sin_precio"] = True
        if tot["llamadas"]:
            agentes.append((etiqueta, modelo, tot))
        for hid, spec in hijos(filas):
            tarea = re.search(r"\bT\d+[a-z-]*\b", spec.get("Prompt", "") or "")
            nombre = spec.get("TypeName") or "subagente"
            rol = spec.get("Role")
            et = nombre + (f" {tarea.group(0)}" if tarea else "") + (f" · {rol}" if rol else "")
            cola.append((hid, et, modelo_de_spec(spec, modelo, cfg), None))

    usd_clp, fuente_dolar = dolar(cfg, a.dolar)
    T = {k: sum(t[k] for _, _, t in agentes) for k in ("llamadas", "entrada", "cache", "salida", "usd")}

    lineas = [
        "## Consumo de la tarea",
        "",
        f"Desde {desde.strftime('%Y-%m-%d %H:%M UTC') if desde else 'el inicio de la conversación'} · "
        f"{len(agentes)} agente(s) · {num(T['llamadas'])} llamadas al modelo",
        "",
        "| Agente | Modelo | Entrada | Entrada en caché | Salida | USD | CLP |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for et, modelo, t in agentes:
        usd = "s/precio" if t["sin_precio"] and not t["usd"] else f"{t['usd']:.4f}"
        lineas.append(f"| {et} | {modelo} | {num(t['entrada'])} | {num(t['cache'])} | {num(t['salida'])} | "
                      f"{usd} | {clp(t['usd'] * usd_clp)} |")
    lineas += [
        f"| **Total** | | **{num(T['entrada'])}** | **{num(T['cache'])}** | **{num(T['salida'])}** | "
        f"**{T['usd']:.4f}** | **{clp(T['usd'] * usd_clp)}** |",
        "",
        f"Tokens de entrada totales: **{num(T['entrada'] + T['cache'])}** "
        f"({num(T['cache'])} leídos de caché, más baratos) · tokens de salida: **{num(T['salida'])}**.",
        f"Dólar: {clp(usd_clp)} por USD ({fuente_dolar}). Precios: tarifa API de Gemini, Standard.",
    ]
    if cfg.get("modalidad", "facturacion") == "facturacion":
        lineas.append("Estimación de lo que se factura en Google Cloud (precio de lista, antes de descuentos "
                      "o créditos; no incluye los modelos de fondo de Antigravity).")
    else:
        lineas.append("Es el costo equivalente a precio de API: con tu plan se descuenta de la cuota; "
                      "solo se paga en dinero si se usan créditos de excedente.")
    if any(t["sin_precio"] for _, _, t in agentes):
        lineas.append("Algún modelo no está en precios.json: sus tokens se cuentan pero no se valorizan.")
    texto = "\n".join(lineas)
    print(texto)
    if a.salida:
        Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
        Path(a.salida).write_text(texto + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
