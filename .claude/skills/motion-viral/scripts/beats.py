#!/usr/bin/env python3
"""
BEATS — detecta BPM e as batidas de uma música (só numpy) para cortar/animar NO TEMPO.
Cortes no beat são um dos maiores "segredos" de edição viral: o cérebro sente o encaixe.

Uso: python beats.py musica.mp3 [--out build/beats.json] [--offset 0]
Saída: {"bpm": 124.0, "beats": [0.48, 0.97, ...], "bars": [...a cada 4 beats...]}
Depois: python tts.py <projeto> --beats build/beats.json   (fins de cena caem no beat)
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import decode  # noqa: E402

SR = 22050


def onset_envelope(x, hop=512, n=2048):
    win = np.hanning(n)
    frames = np.lib.stride_tricks.sliding_window_view(np.pad(x, (n // 2, n // 2)), n)[::hop] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    logm = np.log1p(mag * 10)
    flux = np.maximum(0, np.diff(logm, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(16) / 16, mode="same")
    return np.maximum(flux, 0), SR / hop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--out")
    ap.add_argument("--offset", type=float, default=0.0, help="mesmo offset usado em master_audio --music-offset")
    a = ap.parse_args()
    x = decode(a.audio, sr=SR, channels=1)[:, 0][int(a.offset * SR):]
    env, fr = onset_envelope(x)
    ac = np.correlate(env, env, mode="full")[len(env) - 1:]
    lags = np.arange(len(ac)) / fr
    bpms = 60 / np.maximum(lags, 1e-9)
    mask = (bpms >= 70) & (bpms <= 180)
    w = np.exp(-0.5 * (np.log2(bpms / 120) / 0.9) ** 2)  # leve preferência por ~120 BPM
    lag = np.argmax(np.where(mask, ac * w, 0))
    if 0 < lag < len(ac) - 1:  # interpolação parabólica: precisão sub-frame do período
        y0, y1, y2 = ac[lag - 1], ac[lag], ac[lag + 1]
        den = y0 - 2 * y1 + y2
        lag = lag + (0.5 * (y0 - y2) / den if den else 0)
    period = lag / fr
    bpm = 60 / period
    # fase: escolhe o deslocamento cujo grid soma mais energia de onset
    best, best_phase = -1, 0
    for ph in np.linspace(0, period, 48, endpoint=False):
        idx = np.round(np.arange(ph, len(env) / fr, period) * fr).astype(int)
        s = env[idx[idx < len(env)]].sum()
        if s > best:
            best, best_phase = s, ph
    best_phase = (best_phase + 0.028) % period  # compensa o atraso/adiantamento da janela de análise
    beats = [round(float(t), 3) for t in np.arange(best_phase, len(x) / SR, period)]
    res = {"bpm": round(float(bpm), 1), "period": round(float(period), 4), "beats": beats, "bars": beats[::4]}
    out = Path(a.out) if a.out else Path("beats.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    print(f"[beats] {res['bpm']} BPM • {len(beats)} batidas • primeira em {beats[0] if beats else '-'}s → {out}")


if __name__ == "__main__":
    main()
