#!/usr/bin/env python3
"""
QA FINAL — revisão automática do vídeo pronto, antes de entregar.

Checa:
  TEXTO   ortografia/acentuação (pt/en) de TODO texto que aparece na tela + legendas;
          divergência entre o que é falado e o que é mostrado (números/palavras)
  FONTES  resultado do preflight (fontes carregadas, glifos completos)
  LAYOUT  texto fora da tela / cortado / fora da safe zone (preflight)
  VÍDEO   1080x1920, H.264 yuv420p, fps constante e exato, nº de quadros correto,
          sem tela preta no início (gancho imediato), sem congelamentos longos
  ÁUDIO   AAC 48 kHz, -14 LUFS ±1, true peak <= -1 dBTP, sincronia áudio/vídeo
  VISUAL  gera contact sheet (1 quadro a cada 0,5 s) para revisão visual quadro a quadro

Uso: python qa.py <projeto> [--video out/arquivo.mp4] [--lang pt|en]
Saída: build/qa/qa_report.md (+ sheet.png). Código de saída 1 se houver erro bloqueante.
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import loudness  # noqa: E402

COLLOQUIAL_PT = set("""pra pro pras pros tá tô cê né vc vcs tbm blz ok tipo aí daí bora vamo hein uau nossa caraca galera
youtube tiktok instagram reels shorts story stories feed post posts like likes link bio app apps ia ai chatgpt claude
online offline hack hacks viral virais trend trends fyp pov top setup loop loops replay cta hook hooks b-roll
emoji emojis podcast feedback layout design motion insight insights views stories reel""".split())


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(video):
    js = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", "-count_frames", str(video)]).stdout)
    v = next((s for s in js["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in js["streams"] if s["codec_type"] == "audio"), None)
    return v, a, float(js["format"]["duration"])


def frac(s):
    n, d = s.split("/")
    return float(n) / float(d) if float(d) else 0


def tokenize(text):
    text = re.sub(r"[*_]", "", text)
    return [w for w in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:-[A-Za-zÀ-ÖØ-öø-ÿ]+)*", text)]


def strip_acc(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--video")
    ap.add_argument("--lang", default=None)
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    build = proj / "build"
    qa_dir = build / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((proj / "data.json").read_text())
    lang = a.lang or ("en" if str(data.get("meta", {}).get("tts", {}).get("lang", "pt")).startswith("en") else "pt")
    video = Path(a.video) if a.video else Path((build / "last_output.txt").read_text().strip()) if (build / "last_output.txt").exists() else None
    errors, warns, oks = [], [], []

    # ---------------- TEXTO
    whitelist = {w.lower() for w in (data.get("qa", {}).get("whitelist", []))} | (COLLOQUIAL_PT if lang == "pt" else set())
    texts = []
    tj = qa_dir / "texts.json"
    if tj.exists():
        texts += [t["text"] for t in json.loads(tj.read_text())]
    for sc in data.get("scenes", []):
        for k in ("show", "kicker", "say"):
            if sc.get(k):
                texts.append(sc[k])
    for w in data.get("words", []):
        texts.append(w["w"])
    try:
        from spellchecker import SpellChecker
        sp = SpellChecker(language=lang)
        unknown = {}
        for t in texts:
            for w in tokenize(t):
                lw = w.lower()
                if lw in whitelist or len(lw) < 2 or w.isupper() and len(w) <= 4 and lw not in sp:  # siglas curtas (CEO, SEO)
                    continue
                if lw not in sp:
                    unknown.setdefault(lw, sp.correction(lw))
        accent_errors = {w: c for w, c in unknown.items() if c and strip_acc(c) == strip_acc(w) and c != w}
        others = {w: c for w, c in unknown.items() if w not in accent_errors}
        for w, c in accent_errors.items():
            errors.append(f"ACENTUAÇÃO: '{w}' → '{c}'")
        for w, c in others.items():
            warns.append(f"Palavra não reconhecida: '{w}'" + (f" (sugestão: '{c}')" if c and c != w else "") + " — confirme a grafia ou adicione em data.json → qa.whitelist")
        if not unknown:
            oks.append(f"Ortografia/acentuação OK ({len(texts)} trechos verificados)")
    except ImportError:
        warns.append("pyspellchecker não instalado (pip install pyspellchecker) — revise a ortografia manualmente em build/qa/texts.json")

    drafts = [i for i, sc in enumerate(data.get("scenes", [])) if sc.get("showDraft")]
    if drafts:
        errors.append(f"Cenas {drafts} com texto de tela provisório (showDraft) — reescreva o 'show'")
    # coerência fala x tela (palavras exibidas que não são faladas, exceto números/símbolos)
    for sc in data.get("scenes", []):
        if sc.get("say") and sc.get("show") and sc.get("type") not in ("stat",):
            said = {strip_acc(w.lower()) for w in tokenize(sc["say"])}
            shown = [w for w in tokenize(sc["show"]) if len(w) > 3]
            miss = [w for w in shown if strip_acc(w.lower()) not in said]
            if len(miss) > max(1, len(shown) // 2):
                warns.append(f"Cena {sc.get('id', sc.get('type'))}: texto da tela difere bastante da fala ({', '.join(miss[:5])}) — intencional?")

    # ---------------- PREFLIGHT (fontes/layout)
    pf = qa_dir / "preflight.json"
    if pf.exists():
        p = json.loads(pf.read_text())
        errors += [f"FONTE: {x}" for x in p.get("fontProblems", [])]
        errors += [f"ERRO NA PÁGINA: {x}" for x in p.get("pageErrors", [])]
        for it in p.get("layoutIssues", []):
            (errors if it["level"] == "erro" else warns).append(f"LAYOUT: {it['msg']} (t={', '.join(map(str, it['times'][:5]))}s)")
        if not p.get("fontProblems"):
            oks.append("Fontes carregadas e com todos os glifos (acentos incluídos)")
    else:
        warns.append("Preflight não encontrado (rode render.mjs)")

    # ---------------- VÍDEO
    if video and video.exists():
        v, au, dur = probe(video)
        W, H = data.get("meta", {}).get("width", 1080), data.get("meta", {}).get("height", 1920)
        fps_t = data.get("meta", {}).get("fps", 60)
        if (v["width"], v["height"]) != (W, H):
            errors.append(f"Resolução {v['width']}x{v['height']} (esperado {W}x{H})")
        else:
            oks.append(f"Resolução {W}x{H}")
        if v["codec_name"] != "h264" or v.get("pix_fmt") != "yuv420p":
            errors.append(f"Codec {v['codec_name']}/{v.get('pix_fmt')} (esperado h264/yuv420p)")
        r, avg = frac(v["r_frame_rate"]), frac(v["avg_frame_rate"])
        nb = int(v.get("nb_read_frames") or v.get("nb_frames") or 0)
        exp = round(float(v.get("duration", dur)) * r)
        if abs(r - avg) > 0.01 or abs(nb - exp) > 1:
            errors.append(f"FPS variável ou quadros faltando (r={r:.2f}, média={avg:.2f}, quadros={nb}/{exp})")
        else:
            oks.append(f"{r:.0f} fps constantes, {nb} quadros, sem quadro perdido")
        if r < fps_t - 0.01:
            warns.append(f"fps {r} menor que o alvo {fps_t}")
        # tela preta / congelada
        bd = run(["ffmpeg", "-hide_banner", "-i", str(video), "-t", "1.0", "-vf", "blackdetect=d=0.05:pix_th=0.06", "-an", "-f", "null", "-"]).stderr
        if "black_start:0" in bd:
            errors.append("Começa com tela preta — o gancho precisa aparecer no 1º quadro")
        else:
            oks.append("Gancho visível desde o 1º quadro (sem tela preta)")
        fz = run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "freezedetect=n=0.0008:d=1.2", "-an", "-f", "null", "-"]).stderr
        freezes = re.findall(r"freeze_start: ([\d.]+)", fz)
        if freezes:
            warns.append(f"Tela praticamente parada por >1.2 s em {', '.join(f[:5] for f in freezes[:5])}s — adicione micro-movimento (idle), b-roll ou corte")
        else:
            oks.append("Sem trechos congelados (movimento contínuo)")
        # áudio
        if au:
            if au["codec_name"] != "aac" or int(au["sample_rate"]) != 48000:
                warns.append(f"Áudio {au['codec_name']} {au['sample_rate']} Hz (ideal AAC 48 kHz)")
            lo = loudness(video)
            if lo["lufs"] is None or abs(lo["lufs"] + 14) > 1.0:
                errors.append(f"Loudness {lo['lufs']} LUFS (alvo -14 ±1)")
            else:
                oks.append(f"Loudness {lo['lufs']} LUFS / true peak {lo['true_peak']} dBTP")
            if lo["true_peak"] is not None and lo["true_peak"] > -0.3:
                errors.append(f"True peak {lo['true_peak']} dBTP (vai distorcer na plataforma; rode master_audio com --tp -2.5)")
            elif lo["true_peak"] is not None and lo["true_peak"] > -1.0:
                warns.append(f"True peak {lo['true_peak']} dBTP após AAC (ideal <= -1; aceitável)")
            ad = float(au.get("duration", dur))
            vd = float(v.get("duration", dur))
            if abs(ad - vd) > 0.06:
                warns.append(f"Duração áudio {ad:.3f}s x vídeo {vd:.3f}s")
            else:
                oks.append("Áudio e vídeo com a mesma duração (sincronizados)")
        else:
            warns.append("Vídeo sem trilha de áudio")
        size_mb = video.stat().st_size / 1e6
        mbps = size_mb * 8 / max(dur, 0.1)
        if mbps > 60 or size_mb > 280:
            warns.append(f"Arquivo pesado ({size_mb:.0f} MB, {mbps:.0f} Mbps) — renderize com --maxrate 25M para facilitar o upload")
        else:
            oks.append(f"Tamanho {size_mb:.0f} MB ({mbps:.0f} Mbps) — ok para upload")
        if dur > 60:
            warns.append(f"Duração {dur:.1f}s — para viralizar, 15–35 s costuma reter melhor")
        # contact sheet para revisão visual
        sheet = qa_dir / "sheet.png"
        n = max(1, int(dur / 0.5))
        cols = 8
        rows = (n + cols - 1) // cols
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-vf", f"fps=2,scale=216:-1,tile={cols}x{rows}:padding=4:color=white", "-frames:v", "1", str(sheet)])
        oks.append(f"Contact sheet: {sheet}")
    else:
        warns.append("Vídeo final não encontrado — QA de vídeo/áudio não executado")

    # ---------------- relatório
    status = "REPROVADO ✗" if errors else ("APROVADO COM AVISOS ⚠" if warns else "APROVADO ✓")
    md = [f"# QA — {data.get('meta', {}).get('slug', proj.name)}", "", f"**Status: {status}**", ""]
    if errors:
        md += ["## ✗ Erros (corrigir antes de entregar)"] + [f"- {e}" for e in errors] + [""]
    if warns:
        md += ["## ⚠ Avisos (revisar)"] + [f"- {w}" for w in warns] + [""]
    md += ["## ✓ OK"] + [f"- {o}" for o in oks] + ["", "## Revisão visual obrigatória",
           "- Abra build/qa/sheet.png e os stills de build/stills/ e confira letra por letra: grafia, acentos, quebras de linha, nada cortado, contraste, nada sobreposto."]
    rep = qa_dir / "qa_report.md"
    rep.write_text("\n".join(md))
    print("\n".join(md))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
