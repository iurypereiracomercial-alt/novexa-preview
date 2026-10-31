#!/usr/bin/env python3
"""
GEN IMAGES — gera (ou busca) as imagens das cenas, de graça.

Para cada cena com "image_prompt" (e sem "image" já definida), cria media/sNN.jpg e grava "image" na cena.
Provedores (em ordem, --provider auto):
  pollinations  IA grátis, sem cadastro (modelo FLUX). https://pollinations.ai
  pexels        fotos de banco grátis (licença Pexels, uso comercial ok). Requer PEXELS_API_KEY (grátis em pexels.com/api).
Se nenhum funcionar, o script avisa: use as imagens enviadas pelo usuário ou outra ferramenta de geração.

Campos no data.json:
  "imageStyle": "cinematic photo, moody light, 35mm, high detail"   ← estilo comum (consistência entre cenas)
  cena: "image_prompt": "a smartphone on a desk with neon reflections",
        "image_query": "smartphone desk neon" (opcional, p/ Pexels), "imageLayout": "cover|card|float", "seed": 7

Uso: python gen_images.py <projeto> [--provider auto|pollinations|pexels] [--force] [--only 2,4]
Depois: abra build/images_sheet.png e REVISE (mãos/rostos deformados, texto falso na imagem, marcas d'água).
Refazer uma imagem: mude o "seed" da cena e rode com --only <índice> --force.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

NEG = "no text, no letters, no words, no captions, no watermark, no logo, no signature"
POLL = os.environ.get("MV_POLLINATIONS_URL", "https://image.pollinations.ai/prompt/")
UA = {"User-Agent": "Mozilla/5.0 motion-viral"}


def size_for(layout):
    return {"card": (1080, 1080), "float": (1024, 1024)}.get(layout, (1080, 1920))


def pollinations(prompt, w, h, seed, out):
    url = POLL + urllib.parse.quote(prompt) + "?" + urllib.parse.urlencode({"width": w, "height": h, "seed": seed, "nologo": "true", "model": "flux", "enhance": "false"})
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=150).read()
            if len(data) > 5000:
                out.write_bytes(data)
                return True
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    print(f"   pollinations falhou: {type(last).__name__ if 'last' in dir() else 'resposta vazia'}")
    return False


def pexels(query, w, h, out):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return False
    orient = "portrait" if h > w else "square"
    req = urllib.request.Request("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": query, "orientation": orient, "per_page": 1}), headers={**UA, "Authorization": key})
    try:
        js = json.loads(urllib.request.urlopen(req, timeout=30).read())
        if not js.get("photos"):
            return False
        src = js["photos"][0]["src"]
        url = src.get("portrait" if orient == "portrait" else "large2x") or src["original"]
        out.write_bytes(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        print(f"   pexels: foto de {js['photos'][0].get('photographer')} ({js['photos'][0].get('url')})")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"   pexels falhou: {e}")
        return False


def normalize(out, w, h):
    """Converte para JPEG no tamanho exato (corte central), sRGB."""
    tmp = out.with_suffix(".tmp.jpg")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out), "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}", "-q:v", "2", str(tmp)], check=True)
    tmp.replace(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--provider", default="auto", choices=["auto", "pollinations", "pexels"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    dpath = proj / "data.json"
    data = json.loads(dpath.read_text())
    (proj / "media").mkdir(exist_ok=True)
    only = {int(x) for x in a.only.split(",")} if a.only else None
    style = data.get("imageStyle", "cinematic, high detail, dramatic lighting, vertical composition")
    made, failed = [], []
    for i, sc in enumerate(data.get("scenes", [])):
        if not sc.get("image_prompt") or (only and i not in only) or (sc.get("image") and not a.force):
            continue
        layout = sc.get("imageLayout", "cover")
        w, h = size_for(layout)
        seed = int(sc.get("seed", 1000 + i))
        out = proj / "media" / f"s{i:02d}.jpg"
        prompt = f"{sc['image_prompt']}, {style}, {NEG}"
        print(f"[img] cena {i} ({layout} {w}x{h}): {sc['image_prompt'][:70]}")
        ok = False
        if a.provider in ("auto", "pollinations"):
            ok = pollinations(prompt, w, h, seed, out)
        if not ok and a.provider in ("auto", "pexels"):
            ok = pexels(sc.get("image_query") or sc["image_prompt"], w, h, out)
        if ok:
            normalize(out, w, h)
            sc["image"] = f"media/{out.name}"
            sc.setdefault("imageLayout", layout)
            made.append(out)
        else:
            failed.append(i)
    dpath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    if made:
        (proj / "build").mkdir(exist_ok=True)
        lst = proj / "build" / "_imgs.txt"
        lst.write_text("\n".join(f"file '{m}'" for m in made))
        cols = min(6, len(made))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", f"scale=270:480:force_original_aspect_ratio=decrease,pad=270:480:(ow-iw)/2:(oh-ih)/2:white,tile={cols}x{(len(made) + cols - 1) // cols}:padding=6:color=white", "-frames:v", "1", str(proj / "build" / "images_sheet.png")])
        lst.unlink()
        print(f"[img] {len(made)} imagens → revise build/images_sheet.png")
    if failed:
        print(f"[img] NÃO gerou as cenas {failed}. Opções: (1) rede bloqueia pollinations.ai → defina PEXELS_API_KEY (grátis) "
              f"e rode --provider pexels; (2) peça as imagens ao usuário; (3) use outra ferramenta de geração disponível na sessão "
              f"e salve como media/sNN.jpg com \"image\" na cena; (4) siga sem imagem (só motion).")
        sys.exit(2)


if __name__ == "__main__":
    main()
