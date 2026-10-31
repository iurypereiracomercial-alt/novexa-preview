#!/usr/bin/env python3
"""
USER AUDIO — usa o áudio ENVIADO PELO USUÁRIO no lugar da voz gerada.

Modos:
  voice  narração gravada (ou gerada em outra ferramenta, ex.: ElevenLabs/CapCut).
         Sincroniza as cenas e as palavras com a fala:
           • com Whisper (faster-whisper/openai-whisper instalado): tempos reais de cada palavra;
           • sem Whisper: usa o "say" das cenas (o roteiro) e alinha pelas pausas da gravação.
         Se as cenas não tiverem "say" e houver Whisper, as cenas são criadas a partir da transcrição.
  music  trilha/música do usuário: vira a música do vídeo (com ducking) e gera beats.json para cortar no ritmo.

Uso:
  python user_audio.py <projeto> narracao.mp3 [--mode voice] [--lang pt] [--whisper auto|off]
                       [--model small] [--denoise] [--raw] [--tail 0.5]
  python user_audio.py <projeto> musica.mp3 --mode music [--offset 12.5]
  --raw: não aplica a cadeia de voz no master (use se o áudio já vem mixado/masterizado).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import SR, decode, write_wav  # noqa: E402
from tts import estimate_words, voiced_segments, strip_markup, words_of  # noqa: E402


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9%]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def transcribe(path, lang, model_name):
    """Tenta faster-whisper, depois openai-whisper. Retorna [{w,s,e}] ou None."""
    try:
        from faster_whisper import WhisperModel
        m = WhisperModel(model_name, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(str(path), language=lang, word_timestamps=True, vad_filter=True)
        return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for sg in segs for w in (sg.words or []) if w.word.strip()]
    except ImportError:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"[user_audio] faster-whisper falhou: {e}")
    try:
        import whisper
        m = whisper.load_model(model_name)
        r = m.transcribe(str(path), language=lang, word_timestamps=True)
        return [{"w": w["word"].strip(), "s": round(w["start"], 3), "e": round(w["end"], 3)} for sg in r["segments"] for w in sg.get("words", []) if w["word"].strip()]
    except ImportError:
        return None
    except Exception as e:  # noqa: BLE001
        print(f"[user_audio] whisper falhou: {e}")
        return None


def align_script(script_words, heard):
    """Casa as palavras do roteiro com as ouvidas (ordem preservada); interpola as que não casam."""
    times = [None] * len(script_words)
    p = 0
    for i, w in enumerate(script_words):
        n = norm(w)
        for k in range(p, min(len(heard), p + 6)):
            if norm(heard[k]["w"]) == n or (len(n) > 3 and norm(heard[k]["w"])[:4] == n[:4]):
                times[i] = (heard[k]["s"], heard[k]["e"])
                p = k + 1
                break
    known = [i for i, t in enumerate(times) if t]
    if not known:
        return None
    for i in range(len(times)):
        if times[i] is None:
            a = max([k for k in known if k < i], default=None)
            b = min([k for k in known if k > i], default=None)
            ta = times[a][1] if a is not None else heard[0]["s"]
            tb = times[b][0] if b is not None else heard[-1]["e"]
            na = a if a is not None else -1
            nb = b if b is not None else len(times)
            f0 = (i - na) / (nb - na)
            f1 = (i + 1 - na) / (nb - na)
            times[i] = (ta + (tb - ta) * f0 * 0.98, ta + (tb - ta) * f1 * 0.98)
    return [{"w": w, "s": round(t[0], 3), "e": round(t[1], 3)} for w, t in zip(script_words, times)]


def scenes_from_transcript(words, max_words=7, gap=0.35):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if not nxt or len(cur) >= max_words or re.search(r"[.!?…:]$", w["w"]) or (nxt["s"] - w["e"] > gap) or (re.search(r",$", w["w"]) and len(cur) >= 3):
            out.append(cur)
            cur = []
    scenes = []
    for k, ch in enumerate(out):
        txt = " ".join(w["w"] for w in ch)
        scenes.append({"type": "hook" if k == 0 else ("cta" if k == len(out) - 1 else "text"), "show": txt, "say": txt})
    return scenes, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("audio")
    ap.add_argument("--mode", default="voice", choices=["voice", "music"])
    ap.add_argument("--lang", default="pt")
    ap.add_argument("--whisper", default="auto", choices=["auto", "off"])
    ap.add_argument("--model", default="small", help="tiny|base|small|medium (maior = mais preciso e mais lento)")
    ap.add_argument("--denoise", action="store_true", help="redução de ruído (gravação caseira)")
    ap.add_argument("--raw", action="store_true", help="não tratar a voz no master (áudio já pronto)")
    ap.add_argument("--offset", type=float, default=0.0, help="music: começa a música a partir de X s")
    ap.add_argument("--tail", type=float, default=0.5)
    a = ap.parse_args()

    proj = Path(a.project).resolve()
    dpath = proj / "data.json"
    data = json.loads(dpath.read_text())
    shutil.copy(dpath, proj / "data.json.bak")
    src = Path(a.audio).resolve()
    (proj / "media").mkdir(exist_ok=True)
    (proj / "audio").mkdir(exist_ok=True)

    if a.mode == "music":
        dst = proj / "media" / ("music" + src.suffix.lower())
        shutil.copy(src, dst)
        data["music"] = f"media/{dst.name}"
        data.setdefault("meta", {})["musicOffset"] = a.offset
        dpath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        subprocess.run([sys.executable, str(Path(__file__).parent / "beats.py"), str(dst), "--out", str(proj / "build" / "beats.json"), "--offset", str(a.offset)])
        print("[user_audio] música definida. Monte a timeline: python tts.py <projeto> --engine none --beats build/beats.json "
              "(ou com narração gerada: --engine auto) e depois make.py --skip-tts --music", dst)
        return

    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "in.wav"
        af = "afftdn=nf=-25,highpass=f=60" if a.denoise else "anull"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-af", af, "-ac", "1", "-ar", str(SR), str(clean)], check=True)
        x = decode(clean, channels=1)[:, 0]
    segs = voiced_segments(x)
    lead = max(0.0, segs[0][0] - 0.03)  # tira o silêncio do começo: a voz entra no quadro 0
    x = x[int(lead * SR):]
    segs = [(max(0, s - lead), e - lead) for s, e in segs]
    total_audio = len(x) / SR
    write_wav(proj / "audio" / "vo.wav", x)

    heard = transcribe(proj / "audio" / "vo.wav", a.lang, a.model) if a.whisper == "auto" else None
    scenes = data.get("scenes", [])
    have_say = scenes and all(strip_markup(sc.get("say", "")) for sc in scenes)
    method = None
    if have_say:
        per_scene = [words_of(strip_markup(sc["say"])) for sc in scenes]
        flat = [w for ws in per_scene for w in ws]
        words = align_script(flat, heard) if heard else None
        method = "whisper+roteiro" if words else "pausas+roteiro"
        if not words:
            words = estimate_words(" ".join(flat), x, segs)
        i = 0
        for sc, ws in zip(scenes, per_scene):
            sc["words"] = words[i:i + len(ws)]
            i += len(ws)
    elif heard:
        method = "whisper (cenas criadas da transcrição)"
        new, chunks = scenes_from_transcript(heard)
        for sc, ch in zip(new, chunks):
            sc["words"] = ch
        scenes = data["scenes"] = new
        print("[user_audio] cenas criadas a partir da transcrição — revise 'show' (destaques *x*, números) sem mexer nos tempos.")
    else:
        sys.exit("Sem Whisper e sem roteiro: preencha o campo 'say' de cada cena com o texto exato da narração "
                 "(ou instale: pip install faster-whisper) e rode de novo.")

    for k, sc in enumerate(scenes):
        sc["start"] = 0.0 if k == 0 else round(sc["words"][0]["s"] - 0.04, 3) if sc.get("words") else scenes[k - 1]["end"]
    for k, sc in enumerate(scenes):
        sc["end"] = round(scenes[k + 1]["start"], 3) if k + 1 < len(scenes) else round(total_audio + a.tail, 3)
        if sc["end"] - sc["start"] < 0.5:
            print(f"[user_audio] AVISO: cena {k} muito curta ({sc['end'] - sc['start']:.2f}s) — junte com a vizinha.")
    data["words"] = [w for sc in scenes for w in sc.get("words", [])]
    data["audioDuration"] = round(total_audio + a.tail, 3)
    data["audio"] = "audio/final.wav"
    data.setdefault("meta", {})["tts"] = {"engine": "user", "lang": a.lang, "raw": a.raw, "method": method, "source": src.name}
    dpath.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[user_audio] narração do usuário • sincronia: {method} • {len(data['words'])} palavras • {data['audioDuration']:.2f}s")
    for sc in scenes:
        print(f"   {sc['start']:6.2f}–{sc['end']:6.2f}s  {sc.get('type', 'text'):5s}  {strip_markup(sc.get('say', ''))[:60]}")


if __name__ == "__main__":
    main()
