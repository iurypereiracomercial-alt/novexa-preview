"""Utilitários de áudio compartilhados (só numpy + ffmpeg — sem dependências pesadas)."""
import json
import subprocess
import numpy as np

SR = 48000


def decode(path, sr=SR, channels=2):
    """Decodifica qualquer arquivo de áudio para float32 [n, channels] via ffmpeg."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", str(channels), "-ar", str(sr), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).copy()


def write_wav(path, x, sr=SR, bits=24):
    """Grava float32 [n, ch] em WAV PCM (24-bit por padrão) via ffmpeg."""
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[:, None]
    codec = {16: "pcm_s16le", 24: "pcm_s24le", 32: "pcm_f32le"}[bits]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "f32le", "-ac", str(x.shape[1]), "-ar", str(sr), "-i", "-", "-c:a", codec, str(path)]
    subprocess.run(cmd, input=np.ascontiguousarray(x).tobytes(), check=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def loudness(path):
    """Mede loudness integrado (LUFS) e true peak (dBTP) com o filtro ebur128 do ffmpeg."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    txt = p.stderr
    import re
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", txt)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", txt)
    lra = re.findall(r"LRA:\s+([\d.]+) LU", txt)
    return {"lufs": float(i[-1]) if i else None, "true_peak": float(tp[-1]) if tp else None, "lra": float(lra[-1]) if lra else None}


def onepole_lp(x, fc, sr=SR):
    """Passa-baixa de 1 polo vetorizado o suficiente para SFX curtos."""
    a = np.exp(-2 * np.pi * fc / sr)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def envelope(x, sr=SR, win=0.02):
    """Envelope RMS (mono) com janela em segundos."""
    m = np.abs(x).mean(axis=1) if x.ndim == 2 else np.abs(x)
    n = max(1, int(win * sr))
    k = np.ones(n) / n
    return np.sqrt(np.convolve(m ** 2, k, mode="same"))


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-9))


def undb(d):
    return 10 ** (d / 20)
