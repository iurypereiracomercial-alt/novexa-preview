# Áudio profissional grátis — voz, música, SFX e master

## Índice
1. Motores de voz (TTS) e vozes recomendadas
2. Escrevendo o texto falado (`say`)
3. Cadeia de tratamento da voz
4. Música (fontes grátis e uso correto)
5. SFX (biblioteca procedural + mapa de uso)
6. Loudness e entrega
7. Problemas comuns

---

## 1. TTS
| Motor | Qualidade PT-BR | Offline | Tempos de palavra | Observação |
|---|---|---|---|---|
| **edge-tts** (padrão) | ★★★★★ neural Microsoft | não (precisa de `speech.platform.bing.com`) | reais (WordBoundary) | `pip install edge-tts` |
| **kokoro** (fallback) | ★★★☆ (Apache 2.0) | sim | estimados por pausas/sílabas | `pip install kokoro-onnx soundfile`; modelo baixa sozinho (~120 MB, GitHub) |
| Voz do usuário | — | — | — | grave em WAV, coloque em `audio/vo.wav`, rode com `--engine none` e cenas com `dur` |

Vozes edge recomendadas (confira com `edge-tts --list-voices | grep pt-BR`):
- `pt-BR-AntonioNeural` — masculina, firme (padrão; ótima para kinetic/curiosidades)
- `pt-BR-FranciscaNeural` — feminina, clara e estável
- `pt-BR-ThalitaMultilingualNeural` — feminina, mais natural/expressiva (multilíngue; teste antes)
- Inglês: `en-US-AndrewMultilingualNeural`, `en-US-AvaMultilingualNeural`, `en-US-BrianMultilingualNeural`

Kokoro PT-BR: `pm_alex` (masc.), `pm_santa` (masc.), `pf_dora` (fem.).

Velocidade viral: edge `--rate +8%` a `+15%`; kokoro `--speed 1.08–1.15`. Mais rápido que isso perde clareza.

## 2. Escrevendo o `say`
- Escreva **como se fala**, números por extenso quando a pronúncia puder falhar ("três segundos", "setenta e um por cento").
  O `show` pode ter "3" e "71%" — o motor alinha mesmo assim.
- Frases curtas; vírgula = micro-pausa; ponto = pausa. Evite parênteses, siglas sem explicação e emojis.
- Pontuação expressiva ajuda a entonação: "E o pior?" soa melhor que "e o pior é que".
- Uma frase por cena. Se a frase é longa, divida em 2 cenas (mais pattern interrupts).

## 3. Cadeia da voz (`master_audio.py`)
`highpass 70 Hz` (remove ronco) → `+1,5 dB @200 Hz` (corpo) → `+2,5 dB @3,2 kHz` (presença/inteligibilidade)
→ `de-esser` (chiado de S) → `compressor 3:1, -20 dB, ataque 5 ms` (volume constante) → `limiter`.
Para voz gravada pelo usuário com ruído: aplique antes `afftdn=nf=-25` (redução de ruído do ffmpeg).

## 4. Música
- Fontes grátis: **YouTube Audio Library**, **Pixabay Music**, **Free Music Archive** (filtre CC0/CC-BY), **Uppbeat** (plano grátis).
  Guarde a licença/atribuição junto do projeto quando for CC-BY.
- Perfis comerciais/marca: use apenas música royalty-free ou a Commercial Music Library do TikTok/Meta.
- Sons em alta: adicione dentro do app no momento de postar (e deixe o volume do áudio original adequado).
- Nível: `--music-db -16` (padrão) com ducking de 9 dB sob a voz. Sem voz: `--music-db -8`.
- Pule a introdução morta da música: `--music-offset 12.5` (comece no drop/refrão).
- Corte no beat: `python make.py <proj> --music m.mp3 --beats`.

## 5. SFX
Biblioteca procedural (gerada por síntese, livre de direitos) em `assets/sfx/`:

| Nome | Uso | Disparado automaticamente por |
|---|---|---|
| `whoosh` | transições whip/punch/zoom | `MK.transition` |
| `swoosh` | transições suaves | temas premium/serif |
| `pop` | palavra destacada, legenda-chave | `*destaque*`, `captions.emph` |
| `impact` | golpes, fim de contagem, flash/shake | `stat`, `flash`, `shake` |
| `riser` | antes de revelar número/resultado | início de `stat` |
| `glitch` | transições/destaques tech | tema glitch-tech |
| `click` | digitação | preset `type` |
| `tick` | destaques discretos | tema clean-premium |
| `ding` | conclusão/CTA premium | `impact` no clean-premium |
| `bass` | drop grave | glitch-tech, captions-pop |

Regras: SFX a -7 dB relativo (padrão), nunca em toda palavra, nunca mais alto que a voz. O mixer ignora o mesmo SFX
repetido em < 60 ms. Para SFX próprios (ex.: Pixabay/Freesound CC0), salve `<projeto>/sfx/<nome>.wav` — substitui o procedural.
Cue manual em `custom.js`: `MV.cue(2.4, "ding", 0.8)`.

## 6. Loudness e entrega
- Master: **-14 LUFS integrado**, true peak alvo **-2,3 dBTP** no WAV (depois do AAC fica ≈ -1 dBTP), 48 kHz / 24-bit.
- Vídeo: AAC 320 kbps 48 kHz estéreo. O QA mede o arquivo final (pós-AAC).
- Ouça sempre um trecho no alto-falante do celular: a voz precisa ser 100% inteligível sobre a música.

## 7. Problemas comuns
| Sintoma | Solução |
|---|---|
| edge-tts: `SkewAdjustmentError`/DNS | rede bloqueia o serviço → `--engine kokoro` (automático no `auto`) |
| Palavra pronunciada errado | reescreva foneticamente no `say` (o `show` continua correto) |
| Legenda adiantada/atrasada (kokoro) | estimativa por pausas: use pontuação em cada frase ou prefira edge |
| True peak > -1 após AAC | `master_audio.py --tp -2.8` |
| Música abafando a voz | `--music-db -19 --duck-db 12` |
