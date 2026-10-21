"""Gasto de Antigravity en un período, a partir de los transcripts locales de este PC.

Recorre ~/.gemini/antigravity*/brain/*/.system_generated/logs/transcript.jsonl, suma tokens por
conversación y muestra dónde se va el dinero. Como el transcript no guarda el modelo de la
conversación principal, muestra dos escenarios: todo con el modelo caro (pro) y todo con el
barato (flash). La factura real cae entre ambos (más cerca de "pro" si usas Argon por defecto).

Uso:
  python gasto_mensual.py                          # mes en curso
  python gasto_mensual.py --desde 2026-10-01 --hasta 2026-10-21 --top 15
"""

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PRECIOS = AQUI / "plantilla" / ".agents" / "skills" / "equipo" / "resources" / "precios.json"
UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def tramo(cfg, modelo, dia):
    vigente = None
    for t in sorted(cfg["modelos"][modelo], key=lambda t: t["desde"]):
        if t["desde"] <= dia:
            vigente = t
    return vigente


def analizar(ruta, desde, hasta, cfg):
    pro, flash = cfg["tiers"]["pro"], cfg["tiers"]["flash"]
    t = Counter()
    hijos, pendientes = {}, []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            if not linea.strip():
                continue
            try:
                o = json.loads(linea)
            except json.JSONDecodeError:
                continue
            for tc in o.get("tool_calls") or []:
                if tc.get("name") == "invoke_subagent":
                    specs = (tc.get("args") or {}).get("Subagents") or []
                    if isinstance(specs, str):
                        try:
                            specs = json.loads(specs)
                        except json.JSONDecodeError:
                            specs = []
                    pendientes += specs if isinstance(specs, list) else []
            c = o.get("content")
            if isinstance(c, str) and "Created the following subagents" in c:
                for cid in re.findall(r'"conversationId"\s*:\s*"(' + UUID + ')"', c):
                    spec = pendientes.pop(0) if pendientes else {}
                    hijos[cid] = (spec.get("TypeName") or "?", spec.get("Model") or "sin Model")
                pendientes = []
            dia = (o.get("created_at") or "")[:10]
            if "input_tokens" not in o or not (desde <= dia <= hasta):
                continue
            ent, cac, sal = o.get("input_tokens", 0), o.get("cache_read_tokens", 0), o.get("output_tokens", 0)
            t["llamadas"] += 1
            t["entrada"] += ent
            t["cache"] += cac
            t["salida"] += sal
            t["grandes"] += ent > 50_000
            t["ctx_max"] = max(t["ctx_max"], ent + cac)
            for nombre, modelo in (("usd_pro", pro), ("usd_flash", flash)):
                p = tramo(cfg, modelo, dia)
                t[nombre] += (ent * p["entrada"] + cac * p["cache"] + sal * p["salida"]) / 1_000_000
    return t, hijos


def main():
    hoy = date.today()
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default=hoy.replace(day=1).isoformat())
    ap.add_argument("--hasta", default=hoy.isoformat())
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args()
    cfg = json.loads(PRECIOS.read_text(encoding="utf-8"))

    convs, hijos = {}, {}
    for ruta in (Path.home() / ".gemini").glob("antigravity*/brain/*/.system_generated/logs/transcript.jsonl"):
        t, h = analizar(ruta, a.desde, a.hasta, cfg)
        hijos.update(h)
        if t["llamadas"]:
            convs[ruta.parents[2].name] = t

    T = Counter()
    for t in convs.values():
        T.update({k: v for k, v in t.items() if k != "ctx_max"})
    if not T["llamadas"]:
        sys.exit(f"Sin uso registrado entre {a.desde} y {a.hasta}.")

    p = lambda x: f"{x:,}".replace(",", ".")
    print(f"# Gasto Antigravity {a.desde} → {a.hasta} (transcripts de este PC)\n")
    print(f"- Conversaciones: {len(convs)} ({sum(1 for c in convs if c in hijos)} son subagentes) · llamadas al modelo: {p(T['llamadas'])}")
    print(f"- Entrada nueva: {p(T['entrada'])} · entrada en caché: {p(T['cache'])} · salida: {p(T['salida'])}")
    print(f"- Llamadas con más de 50.000 tokens de entrada nueva: {p(T['grandes'])}")
    print(f"- Escenario todo `pro` ({cfg['tiers']['pro']}): **USD {T['usd_pro']:.2f}** · "
          f"todo `flash` ({cfg['tiers']['flash']}): **USD {T['usd_flash']:.2f}**\n")
    modelos = Counter(hijos[c] for c in convs if c in hijos)
    if modelos:
        print("Subagentes por (tipo, Model): " + ", ".join(f"{k[0]}/{k[1]}×{v}" for k, v in modelos.most_common()))
    print(f"\n## Top {a.top} conversaciones\n")
    print("| Conversación | Tipo | Llamadas | Entrada nueva | Caché | Salida | Contexto máx | USD si pro | USD si flash |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for cid, t in sorted(convs.items(), key=lambda kv: -kv[1]["usd_pro"])[: a.top]:
        tipo = "subagente " + "/".join(hijos[cid]) if cid in hijos else "principal"
        print(f"| {cid[:8]} | {tipo} | {p(t['llamadas'])} | {p(t['entrada'])} | {p(t['cache'])} | {p(t['salida'])} | "
              f"{p(t['ctx_max'])} | {t['usd_pro']:.2f} | {t['usd_flash']:.2f} |")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
