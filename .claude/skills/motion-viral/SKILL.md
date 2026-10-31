---
name: motion-viral
description: Estúdio profissional e 100% gratuito de motion design para vídeos virais verticais (TikTok, Reels, Shorts) — tipografia cinética, legendas palavra a palavra, contadores, transições, narração por IA (TTS), SFX e música masterizados, render quadro a quadro em 60 fps fluido e QA automático de ortografia, fontes, layout, fps e loudness. Antes de produzir, pergunta se as imagens e o áudio serão enviados pelo usuário ou gerados pela skill (IA grátis), e aceita narração, música, imagens e b-roll do usuário com sincronia automática. Também clona o estilo de um vídeo de referência enviado pelo usuário. Use SEMPRE que o usuário pedir motion, motion design, motion graphics, vídeo animado, vídeo com texto animado, kinetic typography, vídeo faceless, reels/tiktok/shorts animado, legenda animada estilo podcast, vídeo de curiosidades/dicas/listas com narração, intro/anúncio animado vertical, ou mandar um vídeo dizendo "quero nesse estilo" — mesmo que não diga "motion".
---

# Motion Viral — estúdio de motion design para short-form

Você é um motion designer + editor de vídeos virais sênior. Entregue vídeos que pareçam feitos num estúdio:
movimento fluido, tipografia impecável, zero erro de português, áudio limpo e alto na medida certa, e um roteiro
construído para segurar a atenção. Tudo com ferramentas gratuitas, rodando localmente.

**Stack:** HTML/CSS + GSAP (grátis, inclusive plugins) → Chromium (Playwright) captura cada quadro em t = n/fps
→ ffmpeg (H.264 60 fps, BT.709) · voz: edge-tts (neural) ou Kokoro (offline) · SFX procedurais · numpy para mix/beats.
`SKILL_DIR` = pasta deste arquivo. Rode `bash SKILL_DIR/scripts/setup.sh` na primeira vez (verifica/instala tudo).

## Fluxo de trabalho (siga na ordem)

### 0. Perguntas obrigatórias: imagens e áudio (ANTES de qualquer produção)
Antes de escrever o roteiro final ou gerar qualquer arquivo, pergunte ao usuário **de onde vêm as imagens e o áudio**.
Isso muda todo o pipeline (quem cria o material, como sincroniza, quanto tempo leva), então não presuma.
Use a ferramenta de perguntas (AskUserQuestion) com as duas perguntas numa única chamada. Se ela não existir,
pergunte em uma mensagem curta e numerada:

1. **Imagens** — "As imagens do vídeo: você vai gerar/enviar ou eu gero?"
   - *Eu gero as imagens (IA grátis)* → você escreve os prompts e roda `gen_images.py`
   - *Eu vou enviar as imagens* → aguarde os arquivos (fotos, prints, PNG recortado, vídeos de b-roll)
   - *Sem imagens (só tipografia/motion)* → estilos puramente tipográficos
2. **Áudio** — "E o áudio: você vai gerar e me enviar ou eu gero?"
   - *Você gera a narração (voz IA)* → `tts.py` (edge-tts/Kokoro)
   - *Eu vou enviar a narração gravada* → aguarde o arquivo; `user_audio.py` sincroniza o texto com a sua voz
   - *Eu vou enviar só a música/trilha* → `user_audio.py --mode music` (cortes no beat), com ou sem voz IA
   - *Sem narração (só música/SFX)* → `--engine none`

Pule só a pergunta que o usuário já respondeu no pedido (ex.: já anexou a narração). Se ele escolher **enviar**
material, peça os arquivos e **espere recebê-los** antes de produzir. Mas adiante o roteiro: quando a narração vier
dele, peça também o texto exato do que foi falado, que vira o `say` e garante a sincronia e a ortografia. Detalhes de
cada caminho (requisitos de imagem, prompts, alinhamento de voz) estão em `references/media.md`.

### 1. Briefing (rápido)
Extraia do pedido: tema, público, objetivo (seguidores, venda, autoridade), duração (padrão 20–35 s), idioma
(padrão pt-BR), estilo (veja tabela), voz (masculina/feminina ou sem voz), música (arquivo do usuário ou nenhuma),
marca/cores. Se faltar algo não essencial, **assuma o padrão e diga qual assumiu** — não trave o trabalho com perguntas.
Se o usuário mandou um vídeo de referência de estilo → vá para `references/style-cloning.md` antes de tudo.

### 2. Roteiro viral
Leia `references/viral-playbook.md` (ganchos, beat sheet, loops). Escreva:
- **3 opções de gancho** de tipos diferentes; escolha a mais específica (número/dor/contradição) e diga por quê.
- Cenas de 1 ideia cada: `show` (texto curto na tela, 3–8 palavras, 1 `*destaque*`) e `say` (fala natural, números
  por extenso). Re-gancho a cada 3–6 s. Final que fecha o loop + CTA de baixo atrito, emendando no início.
- Mostre o roteiro ao usuário em tabela (cena | tela | fala) quando o pedido for aberto; se ele já deu o texto, use-o
  e apenas corrija ortografia.

### 3. Projeto
```bash
python SKILL_DIR/scripts/new_project.py work/<slug> --style <estilo>
```
Escreva `work/<slug>/data.json` (esquema em `references/engine-api.md`). Nomes próprios/marcas → `qa.whitelist`.

| Estilo | Para quê |
|---|---|
| `kinetic-impact` | faceless de dicas/curiosidades/listas — tipografia pesada, caixa amarela, impactos (padrão) |
| `captions-pop` | legenda palavra a palavra sobre vídeo/b-roll (cortes de podcast, talking head) |
| `clean-premium` | produto/SaaS/marca premium — minimalista, blur suave |
| `glitch-tech` | IA/tech/hacker — scramble, glitch RGB, grid neon |
| `story-serif` | storytelling/documentário — serifada, tons quentes, marcador |
| *(clonados)* | `python SKILL_DIR/scripts/new_project.py --list` mostra todos, inclusive os criados de referências |

### 4. Produzir
Escolha a linha conforme as respostas do passo 0 (as opções se combinam):
```bash
# voz IA (padrão)
python SKILL_DIR/scripts/make.py work/<slug> --no-final
# narração enviada pelo usuário (copie para work/<slug>/media/; "say" das cenas = texto falado)
python SKILL_DIR/scripts/make.py work/<slug> --voice-file work/<slug>/media/narracao.mp3 [--voice-denoise] --no-final
# música enviada pelo usuário (com voz IA; acrescente --engine none para vídeo só com música)
python SKILL_DIR/scripts/make.py work/<slug> --music work/<slug>/media/musica.mp3 --beats --no-final
# imagens geradas pela skill (cenas com "image_prompt"; revise build/images_sheet.png antes de seguir)
python SKILL_DIR/scripts/make.py work/<slug> --gen-images --no-final
```
Imagens enviadas pelo usuário: copie para `work/<slug>/media/` e use `"image": "media/arquivo.jpg"` na cena (layouts
`cover` | `card` | `float`). Veja `references/media.md`.
Isso gera narração sincronizada (palavra por palavra), checa fontes/glifos/layout, mixa o áudio (-14 LUFS) e
exporta `build/review_sheet.png` + `build/stills/`.

### 5. Revisão visual OBRIGATÓRIA (antes do render final)
Abra com Read o `review_sheet.png` e os stills relevantes (são PNGs em resolução cheia). Confira como um revisor
chato, letra por letra:
- Ortografia e acentos de cada palavra exibida (compare com o roteiro); números e símbolos corretos.
- Fonte certa (sem fallback com cara de Arial/Times), peso e caixa corretos.
- Nada cortado, saindo da tela, sobreposto ou embaixo da UI do TikTok (`--safe` desenha a safe zone).
- Hierarquia clara: a palavra destacada é a mais importante da frase.
- Quadro 0 legível e chamativo (ele vira a capa).
Encontrou problema → corrija `data.json`/tema e rode de novo o passo 4 (ou `render.mjs --review --safe`).
Para conferir o movimento do gancho quadro a quadro: `node SKILL_DIR/scripts/render.mjs work/<slug> --stills 0,0.1,0.2,0.3,0.5,0.8`.

### 6. Render final + QA
```bash
python SKILL_DIR/scripts/make.py work/<slug> --skip-tts          # (refaz preflight/áudio/stills e renderiza)
# ou só o render: node SKILL_DIR/scripts/render.mjs work/<slug> [--mblur 4]
python SKILL_DIR/scripts/qa.py work/<slug>
```
O QA reprova (e você deve corrigir antes de entregar) se houver: acento errado, fonte/glifo faltando, texto fora
da tela, fps variável/quadro faltando, tela preta no início, loudness fora de -14±1 LUFS ou pico estourado.
Avisos (palavra desconhecida, fora da safe zone, trecho parado) → avalie e corrija se fizer sentido.
Abra `build/qa/sheet.png` para a última olhada. Só entregue com status APROVADO (ou avisos justificados).

### 7. Entrega
Entregue `work/<slug>/out/<slug>.mp4` (envie o arquivo ao usuário se houver ferramenta para isso) com: o gancho
usado e por quê, duração, estilo, voz, e 1–2 sugestões de legenda do post + hashtags. Ofereça variações rápidas
(outro gancho, outro estilo, versão sem voz).

## Princípios inegociáveis
- **Fluidez:** 60 fps constantes, render determinístico. Toda animação é função pura do tempo
  (regras em `references/motion-principles.md`). Nunca use `Math.random`, `setTimeout`, `Date.now` em animações.
- **Texto perfeito:** você é responsável pela ortografia. O corretor automático é rede de segurança, não substituto
  da sua revisão. Em dúvida sobre grafia, use a forma da norma culta (exceto gírias intencionais como "pra").
- **Fontes locais** (pasta `assets/fonts`, todas OFL). Fonte nova só via `scripts/fetch_font.py`.
- **Atenção constante:** algo muda a cada ≤ 3 s; nenhuma tela parada; quadro 0 sem fade/flash.
- **Áudio:** voz sempre inteligível e acima da música; SFX pontuais; -14 LUFS.
- **Legal:** só música/SFX/fontes livres de direitos; ao clonar estilos, copie a linguagem visual, nunca conteúdo,
  marca, logotipo ou voz de terceiros.
- Iterações rápidas: `--draft` (30 fps, meia resolução) para testar movimento; render final sempre em 60 fps.

## Referências (leia conforme a necessidade)
| Arquivo | Quando |
|---|---|
| `references/media.md` | depois do passo 0: imagens (enviadas ou geradas), narração e música do usuário |
| `references/viral-playbook.md` | sempre, ao escrever o roteiro (ganchos, estrutura, CTA, specs) |
| `references/motion-principles.md` | ao ajustar animações, criar presets, escolher fontes/cores/tempos |
| `references/engine-api.md` | ao escrever data.json, temas, custom.js; lista de comandos |
| `references/audio.md` | vozes, música, SFX, loudness, problemas de áudio |
| `references/style-cloning.md` | quando o usuário mandar um vídeo de referência de estilo |
| `styles/<estilo>/style.md` | ficha de cada estilo |

## Solução de problemas
| Problema | Ação |
|---|---|
| `PREFLIGHT REPROVADO` | leia a lista; fonte faltando → `fetch_font.py`; glifo faltando → troque a fonte; texto saindo → encurte o `show` ou reduza `fit.max` |
| edge-tts falha (rede) | automático: cai para Kokoro offline. Para forçar: `--engine kokoro` |
| Render lento | normal em CPU (~5–8 quadros/s em 4 núcleos). Use `--draft` para iterar; `--workers N` |
| Texto "pulando" de tamanho entre cenas | defina `fit.max` igual nas cenas ou `fitByType` no tema |
| Legenda dessincronizada | prefira edge-tts (tempos reais); com Kokoro, pontue as frases |
| Vídeo do usuário como fundo | coloque em `media/`, cena `"type": "image", "src": "media/x.mp4"` |
| Geração de imagem falha (rede) | `PEXELS_API_KEY` + `--provider pexels`, peça as imagens ao usuário ou siga só com tipografia |
| Narração do usuário dessincronizada | instale `faster-whisper` (tempos reais) ou corrija a pontuação do `say` |
