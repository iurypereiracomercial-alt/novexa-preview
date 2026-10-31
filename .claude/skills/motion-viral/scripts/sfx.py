#!/usr/bin/env python3
"""
SFX procedurais — efeitos sonoros gerados por síntese (100% livres de direitos, sempre iguais).
  whoosh, swoosh, pop, impact, riser, glitch, click, tick, ding, bass
Cada efeito tem um "anchor": o instante (s) do golpe dentro do arquivo. O mixer posiciona
o arquivo em (cue - anchor), então o golpe cai EXATAMENTE no quadro da animação.

Uso:  python sfx.py            -> gera/atualiza a biblioteca em assets/sfx/
      python sfx.py --list
Para usar SFX próprios (ex.: baixados do Pixabay/Freesound CC0): coloque <nome>.wav em
<projeto>/sfx/ — eles substituem os procedurais com o mesmo nome.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import SR, write_wav, onepole_lp  # noqa: E402

LIB = Path(__file__).resolve().parent.parent / "assets" / "sfx"
VERSION = 4


def _t(d):
    return np.arange(int(d * SR)) / SR


def _norm(x, peak_db=-1.0):
    m = np.max(np.abs(x)) or 1
    return x / m * 10 ** (peak_db / 20)


def _fade(x, fin=0.002, fout=0.01):
    n_in, n_out = int(fin * SR), int(fout * SR)
    if n_in:
        x[:n_in] *= np.linspace(0, 1, n_in)[:, None] if x.ndim == 2 else np.linspace(0, 1, n_in)
    if n_out:
        x[-n_out:] *= np.linspace(1, 0, n_out)[:, None] if x.ndim == 2 else np.linspace(1, 0, n_out)
    return x


def _sweep_lp(noise, fcs):
    a = np.exp(-2 * np.pi * fcs / SR)
    y = np.empty_like(noise)
    acc = 0.0
    for i in range(len(noise)):
        acc = (1 - a[i]) * noise[i] + a[i] * acc
        y[i] = acc
    return y


def whoosh(dur=0.6, peak=0.6, lo=250, hi=5500, seed=1, width=0.8):
    r = np.random.default_rng(seed)
    t = _t(dur)
    p = t / dur
    env = np.where(p < peak, (p / peak) ** 2.2, np.exp(-((p - peak) / (1 - peak)) * 4.0))
    fc = lo + (hi - lo) * env
    n = r.standard_normal(len(t))
    band = _sweep_lp(n, fc) - _sweep_lp(n, fc * 0.18)
    mono = band * env
    pan = np.clip(0.5 + (p - 0.5) * width, 0, 1)
    x = np.stack([mono * np.cos(pan * np.pi / 2), mono * np.sin(pan * np.pi / 2)], axis=1)
    return _fade(_norm(x, -1)), dur * peak


def pop(f0=1100, f1=260, dur=0.12):
    t = _t(dur)
    f = f1 + (f0 - f1) * np.exp(-t / 0.018)
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-t / 0.035)
    click = np.random.default_rng(3).standard_normal(len(t)) * np.exp(-t / 0.0015) * 0.4
    m = s + click
    return _fade(_norm(np.stack([m, m], 1), -1), 0.0005, 0.01), 0.004


def impact(dur=1.1):
    t = _t(dur)
    f = 42 + 70 * np.exp(-t / 0.07)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.35)
    r = np.random.default_rng(7)
    nz = onepole_lp(r.standard_normal(len(t)), 2200) * np.exp(-t / 0.06) * 3.0
    m = np.tanh((sub * 1.2 + nz) * 1.2)
    return _fade(_norm(np.stack([m, m], 1), -1), 0.0015, 0.05), 0.003


def riser(dur=1.1):
    t = _t(dur)
    p = t / dur
    r = np.random.default_rng(11)
    n = r.standard_normal(len(t))
    fc = 400 + 9000 * p ** 2
    air = (n - _sweep_lp(n, fc * 0.3)) * p ** 2.5 * 0.6
    f = 180 * (2 ** (2.3 * p))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * p ** 2 * 0.5
    m = air + tone
    x = np.stack([m * (1 - 0.2 * p), m * (0.8 + 0.2 * p)], 1)
    return _fade(_norm(x, -1), 0.05, 0.004), 0.0


def glitch(dur=0.22, seed=5):
    r = np.random.default_rng(seed)
    t = _t(dur)
    out = np.zeros(len(t))
    i = 0
    while i < len(t):
        seg = int(r.uniform(0.008, 0.03) * SR)
        f = r.choice([120, 240, 480, 960, 1900])
        kind = r.integers(0, 3)
        tt = np.arange(min(seg, len(t) - i)) / SR
        if kind == 0:
            s = np.sign(np.sin(2 * np.pi * f * tt))
        elif kind == 1:
            s = np.round(r.standard_normal(len(tt)) * 3) / 3
        else:
            s = np.zeros(len(tt))
        out[i:i + len(tt)] = s * r.uniform(0.3, 1)
        i += seg
    out = np.round(out * 8) / 8
    x = np.stack([out, np.roll(out, 90)], 1)
    return _fade(_norm(x, -3), 0.001, 0.01), 0.0


def click(dur=0.03):
    t = _t(dur)
    n = np.random.default_rng(9).standard_normal(len(t)) * np.exp(-t / 0.002)
    s = np.sin(2 * np.pi * 3200 * t) * np.exp(-t / 0.004)
    m = n * 0.5 + s
    return _fade(_norm(np.stack([m, m], 1), -3), 0.0002, 0.005), 0.0


def tick(dur=0.05):
    t = _t(dur)
    m = np.sin(2 * np.pi * 1700 * t) * np.exp(-t / 0.008)
    return _fade(_norm(np.stack([m, m], 1), -3), 0.0002, 0.005), 0.0


def ding(dur=1.4, f=1320):
    t = _t(dur)
    m = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t / (0.5 / k ** 0.5)) for k, a in [(1, 1), (2.76, 0.45), (5.4, 0.2)])
    return _fade(_norm(np.stack([m, m], 1), -2), 0.001, 0.05), 0.002


def bass(dur=0.9):
    t = _t(dur)
    f = 35 + 120 * np.exp(-t / 0.12)
    m = np.tanh(np.sin(2 * np.pi * np.cumsum(f) / SR) * 2.2) * np.exp(-t / 0.4)
    return _fade(_norm(np.stack([m, m], 1), -1), 0.001, 0.05), 0.0


GENERATORS = {
    "whoosh": lambda: whoosh(0.6, 0.62, 250, 6000, 1),
    "swoosh": lambda: whoosh(0.38, 0.55, 600, 7000, 2, 0.5),
    "pop": pop,
    "impact": impact,
    "riser": riser,
    "glitch": glitch,
    "click": click,
    "tick": tick,
    "ding": ding,
    "bass": bass,
}


def ensure_library(force=False):
    LIB.mkdir(parents=True, exist_ok=True)
    idx_path = LIB / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    if not force and idx.get("_version") == VERSION and all((LIB / f"{k}.wav").exists() for k in GENERATORS):
        return idx
    idx = {"_version": VERSION}
    for name, gen in GENERATORS.items():
        x, anchor = gen()
        write_wav(LIB / f"{name}.wav", x)
        idx[name] = {"anchor": round(float(anchor), 4), "dur": round(len(x) / SR, 3)}
    idx_path.write_text(json.dumps(idx, indent=2))
    return idx


if __name__ == "__main__":
    idx = ensure_library(force="--force" in sys.argv)
    if "--list" in sys.argv or True:
        for k, v in idx.items():
            if k != "_version":
                print(f"{k:8s} dur={v['dur']:.2f}s anchor={v['anchor']:.3f}s")
        print("biblioteca:", LIB)
