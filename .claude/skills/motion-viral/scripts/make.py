#!/usr/bin/env python3
"""
MAKE — pipeline completo em um comando:
  0. gen_images.py    (--gen-images) gera as imagens das cenas com "image_prompt"
  1. tts.py           narração IA + timeline   |  user_audio.py (--voice-file) narração enviada pelo usuário
  2. render --preflight-only   fontes, glifos, layout, cues de SFX
  3. master_audio.py  voz tratada + música com ducking + SFX + -14 LUFS
  4. render --review  stills de revisão + contact sheet (para conferência visual)
  5. render           vídeo final 1080x1920 60 fps
  6. qa.py            relatório final (texto, fontes, fps, loudness, sincronia)

Uso:
  python make.py <projeto> [--engine auto|edge|kokoro|none] [--voice X] [--rate +8%]
                 [--music musica.mp3] [--music-db -16] [--beats] [--mblur 4] [--draft]
                 [--skip-tts] [--no-final]   (--no-final: para após os stills, para revisar antes)
                 [--voice-file narracao.mp3 [--transcript t.txt] [--voice-denoise] [--voice-raw]] [--gen-images]
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def step(title, cmd):
    print(f"\n=== {title} ===", flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"\n✗ Falhou em: {title} (código {r.returncode}). Corrija e rode de novo.")
        sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--engine", default="auto")
    ap.add_argument("--voice")
    ap.add_argument("--rate")
    ap.add_argument("--speed")
    ap.add_argument("--lang")
    ap.add_argument("--music")
    ap.add_argument("--music-db")
    ap.add_argument("--music-offset")
    ap.add_argument("--beats", action="store_true", help="corta as cenas no beat da música")
    ap.add_argument("--mblur")
    ap.add_argument("--workers")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--skip-tts", action="store_true")
    ap.add_argument("--no-final", action="store_true")
    ap.add_argument("--voice-file", help="narração gravada/enviada pelo usuário (substitui o TTS)")
    ap.add_argument("--voice-denoise", action="store_true")
    ap.add_argument("--voice-raw", action="store_true", help="não tratar a voz (áudio já masterizado)")
    ap.add_argument("--whisper", default="auto")
    ap.add_argument("--transcript", help="transcrição exata do áudio do usuário (.txt); padrão: <projeto>/transcricao.txt")
    ap.add_argument("--gen-images", action="store_true", help="gera imagens das cenas com image_prompt")
    a = ap.parse_args()
    p = str(Path(a.project).resolve())
    py, node = sys.executable, "node"

    if a.music and a.beats:
        bcmd = [py, str(HERE / "beats.py"), a.music, "--out", str(Path(p) / "build" / "beats.json")]
        if a.music_offset:
            bcmd += ["--offset", a.music_offset]
        step("Beats da música", bcmd)
    if a.gen_images:
        step("0/6 Imagens", [py, str(HERE / "gen_images.py"), p])
        print(f"→ Revise {p}/build/images_sheet.png antes de seguir (deformações, texto falso, marca d'água).")
    if a.voice_file and not a.skip_tts:
        cmd = [py, str(HERE / "user_audio.py"), p, str(Path(a.voice_file).resolve()), "--whisper", a.whisper]
        if a.lang:
            cmd += ["--lang", a.lang.split("-")[0]]
        if a.voice_denoise:
            cmd.append("--denoise")
        if a.voice_raw:
            cmd.append("--raw")
        if a.transcript:
            cmd += ["--transcript", str(Path(a.transcript).resolve())]
        step("1/6 Narração do usuário + timeline", cmd)
    elif not a.skip_tts:
        cmd = [py, str(HERE / "tts.py"), p, "--engine", a.engine]
        for k in ("voice", "rate", "speed", "lang"):
            if getattr(a, k):
                cmd += [f"--{k}", getattr(a, k)]
        if a.music and a.beats:
            cmd += ["--beats", str(Path(p) / "build" / "beats.json")]
        step("1/6 Narração + timeline", cmd)
    import json
    drafts = [i for i, sc in enumerate(json.loads((Path(p) / "data.json").read_text()).get("scenes", [])) if sc.get("showDraft")]
    if drafts:
        print(f"\n✋ Cenas {drafts} ainda com texto de tela provisório (showDraft). Reescreva o 'show' de cada uma "
              f"(curto, 1 *destaque*), apague 'showDraft' e rode de novo com --skip-tts.")
        sys.exit(3)
    step("2/6 Preflight (fontes, glifos, layout)", [node, str(HERE / "render.mjs"), p, "--preflight-only"])
    mcmd = [py, str(HERE / "master_audio.py"), p]
    if a.music:
        mcmd += ["--music", str(Path(a.music).resolve())]
    if a.music_db:
        mcmd += ["--music-db", a.music_db]
    if a.music_offset:
        mcmd += ["--music-offset", a.music_offset]
    step("3/6 Master de áudio", mcmd)
    step("4/6 Stills de revisão", [node, str(HERE / "render.mjs"), p, "--review", "--safe"])
    if a.no_final:
        print(f"\nRevise {p}/build/review_sheet.png e os stills antes do render final.")
        return
    rcmd = [node, str(HERE / "render.mjs"), p]
    if a.draft:
        rcmd.append("--draft")
    if a.mblur:
        rcmd += ["--mblur", a.mblur]
    if a.workers:
        rcmd += ["--workers", a.workers]
    step("5/6 Render final", rcmd)
    r = subprocess.run([py, str(HERE / "qa.py"), p])
    print("\n=== 6/6 QA ===", "APROVADO" if r.returncode == 0 else "REPROVADO — veja build/qa/qa_report.md")
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
