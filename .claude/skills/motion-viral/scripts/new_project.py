#!/usr/bin/env python3
"""
NEW PROJECT — cria a pasta de um vídeo novo a partir de um estilo.

Uso: python new_project.py <pasta> [--style kinetic-impact] [--list]
Cria: <pasta>/index.html (composição), data.json (roteiro de exemplo), audio/, sfx/
"""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

EXAMPLE = {
    "meta": {"fps": 60, "width": 1080, "height": 1920, "slug": "meu-video"},
    "style": "kinetic-impact",
    "theme": {},
    "captions": {"enabled": False, "emph": []},
    "qa": {"whitelist": []},
    "scenes": [
        {"type": "hook", "show": "Seu vídeo *morre* em 3 segundos", "say": "Seu vídeo morre em três segundos."},
        {"type": "text", "show": "E o motivo é *simples*", "say": "E o motivo é simples."},
        {"type": "stat", "show": "decidem nos 3 primeiros segundos", "say": "Setenta e um por cento das pessoas decidem nos três primeiros segundos.", "value": {"to": 71, "suffix": "%"}},
        {"type": "list", "num": "#1", "show": "Mostre o *resultado* primeiro", "say": "Primeiro: mostre o resultado logo de cara."},
        {"type": "cta", "show": "Segue pra *parte 2*", "say": "Segue pra ver a parte dois."},
    ],
}


def styles():
    return sorted(p.name for p in (ROOT / "styles").iterdir() if (p / "theme.js").exists())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", nargs="?")
    ap.add_argument("--style", default="kinetic-impact")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not a.dir:
        for s in styles():
            md = ROOT / "styles" / s / "style.md"
            first = md.read_text().splitlines()[0].lstrip("# ") if md.exists() else ""
            print(f"{s:20s} {first}")
        return
    if a.style not in styles():
        raise SystemExit(f"Estilo '{a.style}' não existe. Disponíveis: {', '.join(styles())}")
    d = Path(a.dir).resolve()
    d.mkdir(parents=True, exist_ok=True)
    for sub in ("audio", "sfx", "media"):
        (d / sub).mkdir(exist_ok=True)
    shutil.copy(ROOT / "assets" / "engine" / "composition.html", d / "index.html")
    if not (d / "data.json").exists():
        ex = json.loads(json.dumps(EXAMPLE))
        ex["style"] = a.style
        ex["meta"]["slug"] = d.name
        (d / "data.json").write_text(json.dumps(ex, ensure_ascii=False, indent=2))
    print(f"Projeto criado em {d} (estilo {a.style}). Edite data.json e rode: python {ROOT}/scripts/make.py {d}")


if __name__ == "__main__":
    main()
