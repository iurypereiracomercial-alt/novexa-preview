#!/usr/bin/env python3
"""
ANALYZE REFERENCE — disseca um vídeo de referência para clonar o estilo.

Gera em <saida>/:
  info.json           resolução, fps, duração, loudness, BPM, cortes, ritmo, paleta
  hook_strip.png      os 2 primeiros segundos quadro a quadro (10 fps) → como o gancho anima
  keyframes.png       1 quadro a cada ~0,5 s (até 48) → tipografia, layout, cores
  cut_frames/         cada corte em resolução cheia (para identificar fonte/tamanho/posição)
  motion.png          gráfico de intensidade de movimento ao longo do tempo (ritmo/energia)
  palette.png         cores dominantes (hex em info.json)
  STYLE_SPEC.md       ficha a preencher (Claude completa olhando as imagens)
Com --compare nosso.mp4: compare.png lado a lado (referência x nosso) nos mesmos instantes.

Uso: python analyze_reference.py <video|url> --out refs/<nome> [--compare out/nosso.mp4]
URLs exigem yt-dlp instalado (pip install yt-dlp). Use apenas para estudo de estilo:
não reutilize trechos, marcas ou personagens do vídeo de referência.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import loudness  # noqa: E402


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def ff(*args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def frames_gray(video, fps=10, w=72):
    """Decodifica quadros pequenos em tons de cinza para medir movimento."""
    h = int(w * 16 / 9)
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def palette(video, k=6):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video), "-vf", "fps=2,scale=48:85,format=rgb24", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    px = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(0)
    px = px[rng.choice(len(px), min(len(px), 40000), replace=False)]
    c = px[rng.choice(len(px), k, replace=False)]
    for _ in range(25):
        lab = np.argmin(((px[:, None] - c[None]) ** 2).sum(-1), 1)
        c = np.array([px[lab == i].mean(0) if np.any(lab == i) else c[i] for i in range(k)])
    share = np.bincount(lab, minlength=k) / len(lab)
    order = np.argsort(-share)
    return [{"hex": "#%02x%02x%02x" % tuple(int(v) for v in c[i]), "share": round(float(share[i]), 3)} for i in order]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare")
    ap.add_argument("--scene-th", type=float, default=0.32)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    src = a.src
    if re.match(r"https?://", src):
        if not shutil.which("yt-dlp"):
            sys.exit("Para URL instale yt-dlp (pip install yt-dlp) ou baixe o vídeo e passe o arquivo.")
        subprocess.run(["yt-dlp", "-f", "mp4/best", "-o", str(out / "reference.%(ext)s"), src], check=True)
        src = str(next(out.glob("reference.*")))
    video = Path(src).resolve()

    pj = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]).stdout)
    v = next(s for s in pj["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in pj["streams"])
    dur = float(pj["format"]["duration"])
    n, d = v["avg_frame_rate"].split("/")
    fps = float(n) / float(d) if float(d) else 0

    # cortes de cena
    sd = run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", f"scale=180:-2,select='gt(scene,{a.scene_th})',showinfo", "-an", "-f", "null", "-"]).stderr
    cuts = [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", sd)]
    shots = np.diff([0] + cuts + [dur]) if dur else []

    # movimento (energia) por 0,1 s
    g = frames_gray(video)
    motion = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2)) if len(g) > 1 else np.zeros(1)
    still_ratio = float(np.mean(motion < 0.6)) if len(motion) else 0

    # imagens de análise
    ff("-i", str(video), "-t", "2", "-vf", "fps=10,scale=216:-1,tile=10x2:padding=4:color=white", "-frames:v", "1", str(out / "hook_strip.png"))
    nk = min(48, max(1, int(dur / 0.5)))
    kf = max(0.5, dur / nk)
    ff("-i", str(video), "-vf", f"fps=1/{kf:.3f},scale=216:-1,tile=8x{(nk + 7) // 8}:padding=4:color=white", "-frames:v", "1", str(out / "keyframes.png"))
    cf = out / "cut_frames"
    cf.mkdir(exist_ok=True)
    for i, t in enumerate([0.3] + [c + 0.25 for c in cuts][:15]):
        ff("-ss", f"{min(t, dur - 0.05):.3f}", "-i", str(video), "-frames:v", "1", str(cf / f"cut{i:02d}_{t:.2f}s.png"))

    # gráfico de movimento (desenhado com numpy → PNG via ffmpeg)
    W, H = 1200, 260
    img = np.full((H, W, 3), 255, np.uint8)
    if len(motion) > 1:
        m = motion / (motion.max() or 1)
        xs = np.linspace(0, W - 1, len(m)).astype(int)
        for x0, x1, y in zip(xs[:-1], xs[1:], m[:-1]):
            img[int(H - 10 - y * (H - 30)):H - 10, x0:max(x1, x0 + 1)] = (40, 90, 255)
        for c in cuts:
            img[:, min(W - 1, int(c / dur * W))] = (255, 40, 80)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-i", "-", str(out / "motion.png")], input=img.tobytes(), check=True)

    pal = palette(video)
    sw = np.concatenate([np.tile(np.array([int(p["hex"][i:i + 2], 16) for i in (1, 3, 5)], np.uint8), (120, max(1, int(p["share"] * 900)), 1)) for p in pal], axis=1)
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{sw.shape[1]}x{sw.shape[0]}", "-i", "-", str(out / "palette.png")], input=np.ascontiguousarray(sw).tobytes(), check=True)

    info = {"file": str(video), "width": v["width"], "height": v["height"], "fps": round(fps, 3), "duration": round(dur, 3),
            "cuts": cuts, "n_shots": len(shots), "avg_shot_s": round(float(np.mean(shots)), 2) if len(shots) else None,
            "cuts_per_10s": round(len(cuts) / dur * 10, 2) if dur else None, "first_cut_s": cuts[0] if cuts else None,
            "still_ratio": round(still_ratio, 3), "palette": pal}
    if has_audio:
        info["audio"] = loudness(video)
        r = run([sys.executable, str(Path(__file__).parent / "beats.py"), str(video), "--out", str(out / "beats.json")])
        if r.returncode == 0:
            info["audio"]["bpm"] = json.loads((out / "beats.json").read_text())["bpm"]
    (out / "info.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))

    spec = f"""# STYLE SPEC — {out.name}
Fonte: {video.name} • {v['width']}x{v['height']} • {fps:.2f} fps • {dur:.1f} s
Cortes: {len(cuts)} (média {info['avg_shot_s']} s por plano, {info['cuts_per_10s']} cortes/10 s) • quadros ~parados: {still_ratio:.0%}
Paleta dominante: {', '.join(p['hex'] for p in pal)}
Áudio: {info.get('audio', 'sem áudio')}

> Preencha olhando hook_strip.png, keyframes.png, cut_frames/ e motion.png.

## 1. Gancho (0–3 s)
- O que aparece no 1º quadro:
- Como o texto entra (preset mais próximo: slam/pop/rise/blur/drop/flip/stretch/wipe/type/scramble/fade):
- Duração da entrada (quadros contados no hook_strip, 10 fps = 0,1 s por quadro):
- Primeiro corte/pattern interrupt em:

## 2. Tipografia
- Fonte(s) (mais parecida em Google Fonts):            peso:        caixa: ALTA/baixa
- Tamanho aprox. (% da largura) e entrelinha:
- Contorno/sombra/brilho:
- Palavras por tela:        posição vertical:

## 3. Cor e textura
- Fundo:        texto:        destaque:        secundário:
- Estilo do destaque (cor / caixa / marcador / sublinhado):
- Grão / vinheta / scanlines / gradiente animado:

## 4. Movimento e ritmo
- Transições entre cenas (punch / whip / flash / shake / glitch / zoom / corte seco):
- Micro-movimento contínuo (idle) sim/não, intensidade:
- Shake / zoom punch nos golpes:
- Ritmo: cenas de ___ s; sincronizado com a voz? com o beat?

## 5. Áudio
- Voz (gênero, energia, velocidade):          música (gênero/BPM):
- SFX audíveis (whoosh, pop, impact, riser, glitch, click, ding):

## 6. Mapeamento → tema
theme.js: colors=…, fonts=…, upper=…, enter=…, exit=…, transitions=…, highlight=…, idle=…, grain=…, sfx=…
Animações que NÃO existem nos presets (implementar em custom.js via MV_CUSTOM):
"""
    (out / "STYLE_SPEC.md").write_text(spec)

    if a.compare:
        ours = Path(a.compare).resolve()
        od = float(json.loads(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(ours)]).stdout)["format"]["duration"])
        ts = np.linspace(0.2, min(dur, od) - 0.1, 8)
        tmp = out / "_c"
        tmp.mkdir(exist_ok=True)
        for i, t in enumerate(ts):
            ff("-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", "scale=240:427:force_original_aspect_ratio=decrease,pad=240:427:(ow-iw)/2:(oh-ih)/2", str(tmp / f"r{i}.png"))
            ff("-ss", f"{t:.3f}", "-i", str(ours), "-frames:v", "1", "-vf", "scale=240:427", str(tmp / f"o{i}.png"))
        ff("-pattern_type", "glob", "-i", str(tmp / "r*.png"), "-vf", "tile=8x1:padding=4:color=white", "-frames:v", "1", str(tmp / "R.png"))
        ff("-pattern_type", "glob", "-i", str(tmp / "o*.png"), "-vf", "tile=8x1:padding=4:color=white", "-frames:v", "1", str(tmp / "O.png"))
        ff("-i", str(tmp / "R.png"), "-i", str(tmp / "O.png"), "-filter_complex", "vstack", str(out / "compare.png"))
        shutil.rmtree(tmp)
        print("comparação (cima = referência, baixo = nosso):", out / "compare.png")

    print(json.dumps({k: info[k] for k in ("width", "height", "fps", "duration", "n_shots", "avg_shot_s", "cuts_per_10s", "still_ratio")}, ensure_ascii=False))
    print("Análise em", out)


if __name__ == "__main__":
    main()
