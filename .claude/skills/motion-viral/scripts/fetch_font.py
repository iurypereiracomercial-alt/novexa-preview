#!/usr/bin/env python3
"""
FETCH FONT — baixa uma fonte do Google Fonts (licença OFL, uso comercial livre) para uso local/offline.

Uso: python fetch_font.py "Bricolage Grotesque" [--weights 400;700;800]
Gera assets/fonts/extra/<slug>/ + <slug>.css. Para usar no projeto, adicione em data.json:
  "meta": {"css": ["/_mv/assets/fonts/extra/<slug>.css"]}
e no tema: fonts: { display: "Bricolage Grotesque" }
O preflight confere se a fonte carregou e se tem todos os glifos (acentos) do texto.
"""
import argparse
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "extra"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30).read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("family")
    ap.add_argument("--weights", default="400;700;800;900")
    a = ap.parse_args()
    slug = re.sub(r"[^a-z0-9]+", "-", a.family.lower()).strip("-")
    out = ROOT / slug
    out.mkdir(parents=True, exist_ok=True)
    css = None
    for w in (a.weights, "400;700", "400"):
        url = f"https://fonts.googleapis.com/css2?family={urllib.parse.quote(a.family)}:wght@{w}&display=block"
        try:
            css = get(url).decode()
            break
        except Exception:  # noqa: BLE001  (peso inexistente → tenta menos pesos)
            continue
    if not css:
        raise SystemExit(f"Fonte '{a.family}' não encontrada no Google Fonts.")
    urls = sorted(set(re.findall(r"url\((https://[^)]+)\)", css)))
    for i, u in enumerate(urls):
        ext = Path(urllib.parse.urlparse(u).path).suffix or ".woff2"
        name = f"{slug}-{i:02d}{ext}"
        (out / name).write_bytes(get(u))
        css = css.replace(u, f"{slug}/{name}")
    css = css.replace("font-display: swap", "font-display: block")
    (ROOT / f"{slug}.css").write_text(css)
    print(f"OK: {len(urls)} arquivos • CSS: /_mv/assets/fonts/extra/{slug}.css • família: \"{a.family}\"")


if __name__ == "__main__":
    main()
