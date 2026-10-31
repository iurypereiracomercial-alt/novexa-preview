#!/usr/bin/env python3
"""
USER AUDIO — usa o áudio ENVIADO PELO USUÁRIO no lugar da voz gerada.

Modos:
  voice  narração gravada (ou gerada em outra ferramenta, ex.: ElevenLabs/CapCut).
         A TRANSCRIÇÃO do usuário (--transcript ou <projeto>/transcricao.txt) é a fonte da verdade do que
         é falado: se as cenas não tiverem "say" igual a ela, as cenas são montadas a partir dela.
         Sincroniza as cenas e as palavras com a fala:
           • com Whisper (faster-whisper/openai-whisper instalado): tempos reais de cada palavra;
           • sem Whisper: usa o "say" das cenas (o roteiro) e alinha pelas pausas da gravação.
         Se as cenas não tiverem "say" e houver Whisper, as cenas são criadas a partir da transcrição.
  music  trilha/música do usuário: vira a música do vídeo (com ducking) e gera beats.json para cortar no ritmo.

Uso:
  python user_audio.py <projeto> narracao.mp3 --transcript transcricao.txt   ← recomendado: texto exato colado pelo usuário
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


SHERPA_DIR = Path.home() / ".cache" / "motion-viral" / "asr"


def transcribe_segments_sherpa(path, segs, lang, model_name):
    """Whisper via sherpa-onnx (modelos no GitHub — funciona até em redes restritas).
    Transcreve cada trecho de fala separado por pausas; devolve [{s, e, text}]."""
    try:
        import sherpa_onnx
    except ImportError:
        return None
    name = f"sherpa-onnx-whisper-{model_name}"
    d = SHERPA_DIR / name
    if not (d / f"{model_name}-tokens.txt").exists():
        SHERPA_DIR.mkdir(parents=True, exist_ok=True)
        url = f"https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{name}.tar.bz2"
        print(f"[user_audio] baixando modelo de transcrição {name} (uma vez só)…")
        try:
            subprocess.run(["curl", "-sSfL", "-o", str(SHERPA_DIR / "m.tar.bz2"), url], check=True)
            subprocess.run(["tar", "xjf", str(SHERPA_DIR / "m.tar.bz2"), "-C", str(SHERPA_DIR)], check=True)
            (SHERPA_DIR / "m.tar.bz2").unlink()
        except Exception as e:  # noqa: BLE001
            print(f"[user_audio] não consegui baixar o modelo: {e}")
            return None
    enc = d / f"{model_name}-encoder.int8.onnx"
    dec = d / f"{model_name}-decoder.int8.onnx"
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(encoder=str(enc), decoder=str(dec), tokens=str(d / f"{model_name}-tokens.txt"), language=lang, task="transcribe", num_threads=4)
    x16 = decode(path, sr=16000, channels=1)[:, 0]
    out = []
    for a, b in segs:
        st = rec.create_stream()
        st.accept_waveform(16000, x16[int(max(0, a - 0.1) * 16000):int((b + 0.1) * 16000)])
        rec.decode_stream(st)
        out.append({"s": a, "e": b, "text": st.result.text.strip()})
    return out


def segment_align(script_words, asr_segs):
    """Liga cada palavra do roteiro ao trecho de fala (pausa a pausa) em que ela foi dita e distribui
    as palavras dentro do trecho pelas sílabas. Precisão de ~0,1 s sem tempos por palavra do ASR."""
    from tts import _distribute
    heard = [(norm(w), i) for i, sg in enumerate(asr_segs) for w in sg["text"].split() if norm(w)]
    idx = [None] * len(script_words)
    p = 0
    for i, w in enumerate(script_words):
        n = norm(w)
        if not n:
            continue
        for k in range(p, min(len(heard), p + 6)):
            h = heard[k][0]
            if h == n or (len(n) > 3 and len(h) > 3 and h[:4] == n[:4]):
                idx[i] = heard[k][1]
                p = k + 1
                break
    known = [i for i, v in enumerate(idx) if v is not None]
    if len(known) < max(3, len(script_words) // 4):
        return None
    for i in range(len(idx)):  # palavras não reconhecidas herdam o trecho vizinho (monotônico)
        if idx[i] is None:
            a = max([k for k in known if k < i], default=None)
            idx[i] = idx[a] if a is not None else idx[min(known)]
    for i in range(1, len(idx)):
        idx[i] = max(idx[i], idx[i - 1])
    out = []
    segs = [(sg["s"], sg["e"]) for sg in asr_segs]
    for j, (a, b) in enumerate(segs):
        ws = [script_words[i] for i in range(len(idx)) if idx[i] == j]
        if ws:
            out += _distribute(ws, a, b, segs)
    return out if len(out) == len(script_words) else None


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


def clean_transcript(text):
    """Texto colado pelo usuário → texto falável: tira emojis/símbolos, troca travessões por vírgula."""
    t = re.sub(r"[\u2600-\u27BF\U0001F000-\U0001FAFF\uFE0F\u200d#*_]", " ", text)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([,.;:!?…])", r"\1", t)
    return t


CONJ = {"e", "mas", "que", "porque", "pois", "quando", "onde", "como", "então", "porém", "enquanto", "se"}
PREP = {"pela", "pelo", "pelas", "pelos", "em", "no", "na", "nos", "nas", "com", "para", "pra", "por", "através", "até",
        "sobre", "entre", "desde", "após", "durante", "sem", "contra"}
NO_END = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "dos", "das", "apenas", "muito", "mais", "menos", "seu", "sua",
          "este", "esta", "esse", "essa", "não", "já", "ainda", "tão", "bem"} | PREP | CONJ


def split_transcript(text, max_words=9, min_words=3):
    """Divide a transcrição em cenas de 1 ideia (~2–3 s de fala cada), cortando nos pontos mais naturais:
    pontuação > conjunção > preposição > meio. Nenhum pedaço com menos de min_words palavras."""
    sentences = [x for x in re.split(r"(?<=[.!?…])\s+", text) if x.strip()]

    def cost(ws, i):
        prev, nxt = ws[i - 1], norm(ws[i])
        kind = 0 if re.search(r"[,;:]$", prev) else 1 if nxt in CONJ else 2.2 if nxt in PREP else 6
        bad_end = 4 if norm(prev) in NO_END else 0  # não termina cena em artigo/preposição/advérbio solto
        return kind + bad_end + abs(i - len(ws) / 2) * 0.35

    def cut(ws):
        if len(ws) <= max_words:
            return [ws]
        cands = list(range(min_words, len(ws) - min_words + 1))
        if not cands:
            return [ws]
        i = min(cands, key=lambda k: cost(ws, k))
        return cut(ws[:i]) + cut(ws[i:])

    chunks = []
    for sen in sentences:
        chunks += cut(sen.split())
    merged = []  # junta pedaços curtos (ex.: "ATENÇÃO:") ao vizinho
    for ch in chunks:
        if merged and (len(ch) < min_words or len(merged[-1]) < min_words) and len(merged[-1]) + len(ch) <= max_words + 3:
            merged[-1] = merged[-1] + ch
        else:
            merged.append(ch)
    out = []
    for k, ws in enumerate(merged):
        txt = " ".join(ws)
        out.append({"type": "hook" if k == 0 else ("cta" if k == len(merged) - 1 else "text"),
                    "show": re.sub(r"[,;:]$", "", txt), "say": txt, "showDraft": True})
    return out


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
    ap.add_argument("--transcript", help="transcrição exata do áudio: arquivo .txt (ou o próprio texto). Fonte da verdade do que é falado")
    ap.add_argument("--max-words", type=int, default=9, help="palavras por cena ao montar cenas a partir da transcrição")
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
    tr_path = proj / "transcricao.txt"
    raw_tr = None
    if a.transcript:
        raw_tr = Path(a.transcript).read_text() if Path(a.transcript).exists() else a.transcript
    elif tr_path.exists():
        raw_tr = tr_path.read_text()
    raw_tr = "\n".join(l for l in (raw_tr or "").splitlines() if not l.lstrip().startswith("#")).strip()
    if raw_tr:
        transcript = clean_transcript(raw_tr)
        tr_path.write_text(raw_tr + "\n")
        joined = clean_transcript(" ".join(strip_markup(sc.get("say", "")) for sc in scenes))
        if not scenes or norm(joined) != norm(transcript):
            if scenes and any(sc.get("say") for sc in scenes):
                print("[user_audio] o 'say' das cenas não bate com a transcrição → cenas refeitas a partir da transcrição (antigas em data.json.bak)")
            scenes = data["scenes"] = split_transcript(transcript, a.max_words)
            print(f"[user_audio] {len(scenes)} cenas criadas da transcrição. Reescreva o 'show' de cada uma (curto, com *destaque*) e apague 'showDraft'.")
    have_say = scenes and all(strip_markup(sc.get("say", "")) for sc in scenes)
    method = None
    if have_say:
        per_scene = [words_of(strip_markup(sc["say"])) for sc in scenes]
        flat = [w for ws in per_scene for w in ws]
        words = align_script(flat, heard) if heard else None
        method = "whisper+roteiro" if words else None
        if not words and a.whisper == "auto":
            asr = transcribe_segments_sherpa(proj / "audio" / "vo.wav", segs, a.lang, a.model)
            words = segment_align(flat, asr) if asr else None
            if asr:
                heard_w = {norm(w) for sg in asr for w in sg["text"].split()}
                sw = [norm(w) for w in flat if len(norm(w)) > 3]
                ratio = sum(w in heard_w for w in sw) / max(1, len(sw))
                print(f"[user_audio] conferência transcrição x áudio: {ratio:.0%} das palavras reconhecidas")
                if ratio < 0.6:
                    print("[user_audio] AVISO: a transcrição parece NÃO corresponder ao áudio — confirme com o usuário antes de seguir.")
            if words:
                method = "sherpa-whisper (trechos)+roteiro"
                (proj / "build").mkdir(exist_ok=True)
                (proj / "build" / "transcript.json").write_text(json.dumps(asr, ensure_ascii=False, indent=1))
        if not words:
            method = "pausas+roteiro"
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
        sys.exit("Sem transcrição: peça ao usuário o texto exato do áudio e passe com --transcript (ou salve em transcricao.txt), "
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
