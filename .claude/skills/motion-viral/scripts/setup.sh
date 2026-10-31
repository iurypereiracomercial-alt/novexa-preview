#!/usr/bin/env bash
# Instala/verifica tudo que a skill motion-viral usa (tudo gratuito). Seguro rodar várias vezes.
set -u
ok(){ printf "  ✓ %s\n" "$1"; } ; bad(){ printf "  ✗ %s\n" "$1"; MISSING=1; } ; MISSING=0
echo "== Ferramentas do sistema"
command -v ffmpeg >/dev/null && ok "ffmpeg $(ffmpeg -version | head -1 | cut -d' ' -f3)" || bad "ffmpeg (instale: apt install ffmpeg | brew install ffmpeg | winget install ffmpeg)"
command -v node >/dev/null && ok "node $(node -v)" || bad "Node.js 18+ (https://nodejs.org)"
command -v python3 >/dev/null && ok "python $(python3 --version | cut -d' ' -f2)" || bad "Python 3.10+"
echo "== Python"
python3 -m pip install -q --disable-pip-version-check numpy edge-tts pyspellchecker kokoro-onnx soundfile 2>/dev/null \
  && ok "numpy, edge-tts, pyspellchecker, kokoro-onnx, soundfile" || bad "pip install numpy edge-tts pyspellchecker kokoro-onnx soundfile"
echo "== Opcional: Whisper (sincronia exata com narração enviada pelo usuário)"
python3 -c "import faster_whisper" 2>/dev/null && ok "faster-whisper" || { python3 -m pip install -q sherpa-onnx 2>/dev/null && ok "sherpa-onnx (Whisper via GitHub)" || echo "  ~ opcional: pip install faster-whisper (ou sherpa-onnx)"; }
echo "== Playwright/Chromium"
if node -e "require('playwright')" 2>/dev/null; then ok "playwright"; else
  npm i -g playwright >/dev/null 2>&1 && npx playwright install chromium >/dev/null 2>&1 && ok "playwright instalado" || bad "npm i -g playwright && npx playwright install chromium"; fi
echo "== SFX"
python3 "$(dirname "$0")/sfx.py" >/dev/null && ok "biblioteca de SFX gerada"
echo "== Rede (opcional)"
python3 - <<'PY' 2>/dev/null && ok "edge-tts acessível (voz neural online)" || echo "  ~ edge-tts sem acesso → será usado kokoro (offline)"
import asyncio, os, edge_tts
async def t():
    c = edge_tts.Communicate("ok", "pt-BR-AntonioNeural", proxy=os.environ.get("HTTPS_PROXY"))
    async for ch in c.stream():
        if ch["type"] == "audio": return
asyncio.run(asyncio.wait_for(t(), 15))
PY
[ $MISSING = 0 ] && echo "Pronto." || echo "Instale os itens marcados com ✗."
