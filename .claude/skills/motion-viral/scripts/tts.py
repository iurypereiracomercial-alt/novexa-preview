#!/usr/bin/env python3
"""
TTS + TIMELINE — gera a narração cena a cena e sincroniza o data.json com a voz.

Para cada cena com "say" (texto falado), sintetiza a voz, mede a duração exata e grava
os tempos de cada palavra (para o texto/legenda aparecer NO MESMO quadro em que é falado).
Cenas sem "say" usam "dur" ou o tempo de leitura automático.

Motores (todos gratuitos):
  edge   — vozes neurais da Microsoft (edge-tts). Melhor qualidade em PT-BR, tempos de palavra
           reais. Precisa de internet (speech.platform.bing.com).
  kokoro — modelo local open-source (Apache 2.0, kokoro-onnx). Funciona offline. Tempos de
           palavra estimados (alinhados por pausas).
  auto   — tenta edge, se falhar usa kokoro.  |  none — sem voz (só música/SFX).

Uso:
  python tts.py <projeto> [--engine auto] [--voice pt-BR-AntonioNeural] [--rate +8%]
                [--speed 1.08] [--gap 0.06] [--tail 0.5] [--lang pt-BR] [--beats build/beats.json]
Saídas: <projeto>/audio/vo.wav, data.json atualizado (start/end/words de cada cena, words globais).
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import SR, decode, write_wav, envelope, db  # noqa: E402

KOKORO_DIR = Path(os.environ.get("MV_KOKORO_DIR", Path.home() / ".cache" / "motion-viral" / "kokoro"))
KOKORO_FILES = {
    "kokoro-v1.0.int8.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
DEFAULTS = {
    "pt-BR": {"edge": "pt-BR-AntonioNeural", "kokoro": "pm_alex", "klang": "pt-br"},
    "en-US": {"edge": "en-US-AndrewMultilingualNeural", "kokoro": "am_michael", "klang": "en-us"},
    "es-ES": {"edge": "es-MX-JorgeNeural", "kokoro": "em_alex", "klang": "es"},
}


def strip_markup(s):
    return re.sub(r"[*_]", "", s or "").replace("\n", " ").strip()


def words_of(text):
    return [w for w in re.split(r"\s+", text.strip()) if w]


def syllables(w):
    n = unicodedata.normalize("NFD", w.lower())
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    if re.fullmatch(r"[\d.,%]+", n):
        return max(2, len(re.sub(r"\D", "", n)) * 2)  # números falados são longos
    return max(1, len(re.findall(r"[aeiouy]+", n)))


# ------------------------------------------------------------------ EDGE
async def _edge(text, voice, rate, pitch, out_mp3):
    import edge_tts
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    c = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary", proxy=proxy)
    words = []
    with open(out_mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append({"w": ch["text"], "s": round(s, 3), "e": round(s + ch["duration"] / 1e7, 3)})
    return words


def synth_edge(text, voice, rate, pitch, tmp):
    mp3 = Path(tmp) / "edge.mp3"
    words = asyncio.run(_edge(text, voice, rate, pitch, mp3))
    if not mp3.exists() or mp3.stat().st_size < 1000:
        raise RuntimeError("edge-tts não retornou áudio")
    return decode(mp3, channels=1)[:, 0], words


# ------------------------------------------------------------------ KOKORO
_kokoro = None


def ensure_kokoro():
    KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in KOKORO_FILES.items():
        p = KOKORO_DIR / name
        if not p.exists():
            print(f"[tts] baixando {name} (uma vez só)…")
            urllib.request.urlretrieve(url, p)
    return KOKORO_DIR / "kokoro-v1.0.int8.onnx", KOKORO_DIR / "voices-v1.0.bin"


def synth_kokoro(text, voice, speed, lang):
    global _kokoro
    from kokoro_onnx import Kokoro
    if _kokoro is None:
        m, v = ensure_kokoro()
        _kokoro = Kokoro(str(m), str(v))
    samples, sr = _kokoro.create(text, voice=voice, speed=speed, lang=lang)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    write_wav(tmp, np.asarray(samples, dtype=np.float32), sr=sr, bits=32)
    x = decode(tmp, channels=1)[:, 0]
    os.unlink(tmp)
    return x, estimate_words(text, x)


def voiced_segments(x, min_gap=0.12):
    """Trechos com voz (s), separados por pausas >= min_gap."""
    env = db(envelope(x, win=0.015))
    voiced = env > (np.max(env) - 38)
    hop = int(0.01 * SR)
    v = voiced[::hop]
    segs, cur = [], None
    for i, on in enumerate(v):
        if on and cur is None:
            cur = i
        if not on and cur is not None:
            segs.append([cur, i])
            cur = None
    if cur is not None:
        segs.append([cur, len(v)])
    merged = []
    for sg in segs:
        if merged and sg[0] - merged[-1][1] < int(min_gap * 100):
            merged[-1][1] = sg[1]
        else:
            merged.append(sg)
    return [(a * hop / SR, b * hop / SR) for a, b in merged if b - a > 3] or [(0.0, len(x) / SR)]


def _distribute(ws, t0, t1, segs):
    """Distribui palavras entre t0..t1 proporcional às sílabas, pulando as pausas internas."""
    parts = [(max(a, t0), min(b, t1)) for a, b in segs if b > t0 and a < t1] or [(t0, t1)]
    total = sum(b - a for a, b in parts) or 1e-6
    def real(v):  # tempo "falado" → tempo real
        for a, b in parts:
            if v <= b - a:
                return a + v
            v -= b - a
        return parts[-1][1]
    wts = np.array([syllables(w) for w in ws], dtype=float)
    cum = np.concatenate([[0], np.cumsum(wts) / wts.sum()]) * total
    return [{"w": w, "s": round(real(cum[k] + 1e-4), 3), "e": round(real(cum[k + 1]), 3)} for k, w in enumerate(ws)]


def estimate_words(text, x, segs=None):
    """Estima o tempo de cada palavra sem reconhecimento de fala:
    1) mapeia as palavras pelo tempo de fala (proporcional às sílabas);
    2) "imanta" cada fim de frase (pontuação) à pausa real mais próxima do áudio;
    3) distribui as palavras de cada frase dentro do seu trecho, pulando pausas.
    Funciona bem para TTS e para narrações gravadas com pausas naturais."""
    segs = segs or voiced_segments(x)
    ws = words_of(text)
    if not ws:
        return []
    gaps = [(segs[i][1], segs[i + 1][0]) for i in range(len(segs) - 1)]
    V = sum(b - a for a, b in segs)
    def real(v):
        for a, b in segs:
            if v <= b - a:
                return a + v
            v -= b - a
        return segs[-1][1]
    wts = np.array([syllables(w) for w in ws], dtype=float)
    cum = np.concatenate([[0], np.cumsum(wts) / wts.sum()]) * V
    bounds = [k + 1 for k, w in enumerate(ws[:-1]) if re.search(r"[,.;:!?…]$", w)]
    cuts, used = [], -1
    for k in bounds:
        t = real(cum[k])
        cands = [(abs((g0 + g1) / 2 - t), gi) for gi, (g0, g1) in enumerate(gaps) if gi > used and abs((g0 + g1) / 2 - t) < 0.9]
        if cands:
            gi = min(cands)[1]
            used = gi
            cuts.append((k, gaps[gi][0], gaps[gi][1]))
    out, k0, ts = [], 0, segs[0][0]
    for k, g0, g1 in cuts + [(len(ws), segs[-1][1], None)]:
        out += _distribute(ws[k0:k], ts, g0, segs)
        k0, ts = k, g1
    return out


# ------------------------------------------------------------------ util
def trim(x, words, pad=0.03):
    env = db(envelope(x, win=0.01))
    on = np.where(env > (np.max(env) - 45))[0]
    if not len(on):
        return x, words
    a = max(0, on[0] - int(pad * SR))
    b = min(len(x), on[-1] + int(pad * 2 * SR))
    off = a / SR
    return x[a:b], [{"w": w["w"], "s": round(max(0, w["s"] - off), 3), "e": round(max(0, w["e"] - off), 3)} for w in words]


def reading_time(show):
    n = len(words_of(strip_markup(show)))
    return max(1.1, 0.45 + 0.3 * n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--engine", default="auto", choices=["auto", "edge", "kokoro", "none"])
    ap.add_argument("--lang", default="pt-BR")
    ap.add_argument("--voice")
    ap.add_argument("--rate", default="+8%", help="edge: velocidade (+8%% = mais dinâmico)")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--speed", type=float, default=1.08, help="kokoro: velocidade")
    ap.add_argument("--gap", type=float, default=0.06, help="respiro entre cenas (s)")
    ap.add_argument("--tail", type=float, default=0.5, help="segura a última cena (s)")
    ap.add_argument("--beats", help="beats.json (scripts/beats.py) para cortar no tempo da música")
    a = ap.parse_args()

    proj = Path(a.project).resolve()
    dpath = proj / "data.json"
    data = json.loads(dpath.read_text())
    shutil.copy(dpath, proj / "data.json.bak")
    d = DEFAULTS.get(a.lang, DEFAULTS["pt-BR"])
    scenes = data.get("scenes", [])
    beats = json.loads(Path(a.beats).read_text())["beats"] if a.beats else None
    engine = a.engine
    if engine != "none" and not any(sc.get("say") for sc in scenes):
        engine = "none"

    chunks, all_words, cursor = [], [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        for i, sc in enumerate(scenes):
            say = strip_markup(sc.get("say", ""))
            x, words = None, []
            if say and engine != "none":
                if engine in ("auto", "edge"):
                    try:
                        x, words = synth_edge(say, a.voice if (a.voice and "Neural" in a.voice) else d["edge"], a.rate, a.pitch, tmp)
                        used = "edge"
                    except Exception as e:  # noqa: BLE001
                        if engine == "edge":
                            raise
                        print(f"[tts] edge-tts indisponível ({type(e).__name__}); usando kokoro (offline)")
                        engine = "kokoro"
                if engine == "kokoro":
                    x, words = synth_kokoro(say, a.voice if (a.voice and "Neural" not in a.voice) else d["kokoro"], a.speed, d["klang"])
                    used = "kokoro"
                if engine == "auto":
                    engine = used
                x, words = trim(x, words)
            vo_len = len(x) / SR if x is not None else 0
            min_len = sc.get("dur") or (reading_time(sc.get("show", "")) if x is None else 0.9)
            dur = max(vo_len + a.gap, min_len) + float(sc.get("hold", 0))
            if i == len(scenes) - 1:
                dur += a.tail
            end = cursor + dur
            if beats:  # corta no beat mais próximo que não encurte a fala
                cands = [b for b in beats if b >= cursor + max(vo_len, 0.6)]
                if cands:
                    end = min(cands, key=lambda b: abs(b - end) if b >= cursor + vo_len else 1e9)
            sc["start"], sc["end"] = round(cursor, 3), round(end, 3)
            if x is not None:
                gw = [{"w": w["w"], "s": round(cursor + w["s"], 3), "e": round(cursor + w["e"], 3)} for w in words]
                sc["words"] = gw
                all_words += gw
                chunks.append((cursor, x))
            else:
                sc.pop("words", None)
            cursor = end

    total = cursor
    proj.joinpath("audio").mkdir(exist_ok=True)
    if chunks:
        vo = np.zeros(int(total * SR) + SR, dtype=np.float32)
        for t0, x in chunks:
            i0 = int(round(t0 * SR))
            vo[i0:i0 + len(x)] += x[: len(vo) - i0]
        vo = vo[: int(total * SR)]
        write_wav(proj / "audio" / "vo.wav", vo)
    data["words"] = all_words
    data["audioDuration"] = round(total, 3)
    data["audio"] = "audio/final.wav"
    data.setdefault("meta", {})["tts"] = {"engine": engine, "lang": a.lang}
    dpath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[tts] motor={engine} • {len(scenes)} cenas • {len(all_words)} palavras • duração {total:.2f}s")
    for sc in scenes:
        print(f"   {sc['start']:6.2f}–{sc['end']:6.2f}s  {sc.get('type', 'text'):5s}  {strip_markup(sc.get('say') or sc.get('show', ''))[:60]}")


if __name__ == "__main__":
    main()
