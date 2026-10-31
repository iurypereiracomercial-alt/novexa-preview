#!/usr/bin/env python3
"""
MASTER DE ÁUDIO — voz tratada + música com ducking + SFX sincronizados + loudness de plataforma.

Cadeia da voz (padrão de estúdio para short-form):
  passa-alta 70 Hz → corpo +1.5 dB @200 Hz → presença +2.5 dB @3.2 kHz → de-esser → compressor 3:1 → limiter
Música: fade in/out, -16 dB sob a voz, ducking automático (abaixa ~9 dB quando há fala).
SFX: posicionados pelos cues que a animação registrou (build/cues.json), golpe no quadro exato.
Master final: loudnorm em 2 passadas → -14 LUFS integrado, true peak -1 dBTP, 48 kHz / 24-bit.

Uso:
  python master_audio.py <projeto> [--music musica.mp3] [--music-db -16] [--duck-db 9]
                         [--sfx-db -7] [--no-sfx] [--lufs -14] [--tp -1.0]
Pré-requisito: build/cues.json (gerado por `node render.mjs <projeto> --preflight-only`).
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from audiolib import SR, decode, write_wav, envelope, loudness, undb  # noqa: E402
from sfx import ensure_library, LIB  # noqa: E402

VO_CHAIN = ("highpass=f=70:p=2,"
            "equalizer=f=200:t=q:w=1:g=1.5,"
            "equalizer=f=3200:t=q:w=1.2:g=2.5,"
            "deesser=i=0.35:m=0.5:f=0.5,"
            "acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=3dB:knee=4,"
            "alimiter=limit=0.89:attack=3:release=50:level=false")


def ff(args):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--music")
    ap.add_argument("--music-db", type=float, default=-16.0)
    ap.add_argument("--music-offset", type=float, default=0.0, help="começa a música a partir de X s (pule a intro)")
    ap.add_argument("--duck-db", type=float, default=9.0)
    ap.add_argument("--sfx-db", type=float, default=-7.0)
    ap.add_argument("--no-sfx", action="store_true")
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--tp", type=float, default=-2.3, help="true peak alvo; -1.5 deixa folga p/ o encode AAC não estourar")
    a = ap.parse_args()

    proj = Path(a.project).resolve()
    data = json.loads((proj / "data.json").read_text())
    meta_p = proj / "build" / "meta.json"
    total = json.loads(meta_p.read_text())["duration"] if meta_p.exists() else data.get("audioDuration") or 0
    if not total:
        sys.exit("Duração desconhecida: rode tts.py e `render.mjs --preflight-only` antes.")
    n = int(round(total * SR))
    mix = np.zeros((n, 2), dtype=np.float32)
    report = {"duration": total}

    with tempfile.TemporaryDirectory() as tmp:
        # ---- voz
        vo_path = proj / "audio" / "vo.wav"
        vo = None
        if vo_path.exists():
            proc = Path(tmp) / "vo_proc.wav"
            ff(["-i", str(vo_path), "-af", VO_CHAIN, "-ar", str(SR), "-ac", "2", "-c:a", "pcm_f32le", str(proc)])
            vo = decode(proc)[:n]
            mix[: len(vo)] += vo
            report["voice"] = True

        # ---- música com ducking
        music = a.music or data.get("music")
        if music:
            mpath = Path(music) if Path(music).is_absolute() else (proj / music)
            m = decode(mpath)
            start = int(a.music_offset * SR)
            m = m[start:]
            if len(m) < n:  # loop se a música for curta
                m = np.concatenate([m] * (n // max(len(m), 1) + 1))
            m = m[:n].copy()
            fi, fo = int(0.25 * SR), int(min(1.2, total / 4) * SR)
            m[:fi] *= np.linspace(0, 1, fi)[:, None]
            m[-fo:] *= np.linspace(1, 0, fo)[:, None]
            # normaliza a música para ~-14 LUFS aprox. via RMS, depois aplica o nível relativo
            rms = np.sqrt(np.mean(m ** 2)) or 1
            m *= (0.2 / rms) * undb(a.music_db + 6)
            if vo is not None:
                hop = int(0.01 * SR)
                env = envelope(vo, win=0.03)[::hop]
                active = (env > (env.max() * 0.08)).astype(float)
                g = np.zeros_like(active)
                acc = 0.0
                for i, v in enumerate(active):  # attack 40 ms, release 300 ms
                    k = 0.22 if v > acc else 0.033
                    acc += (v - acc) * k
                    g[i] = acc
                gain = undb(-a.duck_db * np.interp(np.arange(n) / hop, np.arange(len(g)), g))
                m *= gain[:, None].astype(np.float32)
            mix += m
            report["music"] = str(mpath.name)

        # ---- SFX nos cues da animação
        cues_p = proj / "build" / "cues.json"
        if not a.no_sfx and cues_p.exists():
            idx = ensure_library()
            cues = json.loads(cues_p.read_text())
            cache, placed = {}, 0
            last_t = {}
            for c in cues:
                name = c["sfx"]
                if name in last_t and c["t"] - last_t[name] < 0.06:  # evita metralhadora de SFX iguais
                    continue
                last_t[name] = c["t"]
                custom = proj / "sfx" / f"{name}.wav"
                src = custom if custom.exists() else (LIB / f"{name}.wav")
                if not src.exists():
                    print(f"[master] SFX desconhecido: {name}")
                    continue
                if src not in cache:
                    cache[src] = decode(src)
                x = cache[src]
                anchor = 0.0 if custom.exists() else idx.get(name, {}).get("anchor", 0.0)
                # golpe no quadro 0 estoura o encoder AAC (priming): adia no máx. 3 quadros (imperceptível)
                i0 = int(round((max(c["t"], 0.05) - anchor) * SR))
                if i0 < 0:
                    x = x[-i0:]
                    i0 = 0
                seg = x[: max(0, n - i0)]
                mix[i0:i0 + len(seg)] += seg * undb(a.sfx_db) * float(c.get("gain", 1))
                placed += 1
            report["sfx"] = placed

        if not np.any(mix):
            sys.exit("Nada para mixar (sem voz, música ou SFX).")
        # micro fade de 15 ms no início/fim: evita estouro do encoder AAC num golpe exatamente no quadro 0
        f8 = int(0.015 * SR)
        mix[:f8] *= np.linspace(0, 1, f8)[:, None]
        mix[-f8:] *= np.linspace(1, 0, f8)[:, None]
        pre = Path(tmp) / "premix.wav"
        peak = np.max(np.abs(mix))
        if peak > 0.98:
            mix *= 0.98 / peak
        write_wav(pre, mix, bits=32)

        # ---- loudnorm 2 passadas
        p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pre), "-af", f"loudnorm=I={a.lufs}:TP={a.tp}:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
        js = p.stderr[p.stderr.rfind("{"): p.stderr.rfind("}") + 1]
        mz = json.loads(js)
        out = proj / "audio" / "final.wav"
        ln = (f"loudnorm=I={a.lufs}:TP={a.tp}:LRA=11:measured_I={mz['input_i']}:measured_TP={mz['input_tp']}:"
              f"measured_LRA={mz['input_lra']}:measured_thresh={mz['input_thresh']}:offset={mz['target_offset']}:linear=true")
        # limiter com oversampling 4x = controla true peak (picos entre amostras que o AAC faria estourar)
        lim = f"aresample={SR * 4},alimiter=limit={10 ** ((a.tp - 0.3) / 20):.4f}:attack=1:release=40:level=false,aresample={SR}"
        ff(["-i", str(pre), "-af", f"{ln},{lim}", "-ar", str(SR), "-c:a", "pcm_s24le", str(out)])

    lo = loudness(out)
    report.update(lo)
    (proj / "build").mkdir(exist_ok=True)
    (proj / "build" / "audio_report.json").write_text(json.dumps(report, indent=2))
    ok = lo["lufs"] is not None and abs(lo["lufs"] - a.lufs) <= 1.0 and (lo["true_peak"] or 0) <= -1.0
    print(f"[master] {out}  •  {lo['lufs']} LUFS  •  true peak {lo['true_peak']} dBTP  •  SFX {report.get('sfx', 0)}  •  {'OK ✓' if ok else 'REVISAR ✗'}")


if __name__ == "__main__":
    main()
