# Engine API — data.json, temas, cenas e MotionKit

## Índice
1. Estrutura de um projeto
2. data.json (esquema completo)
3. Tipos de cena
4. Opções de tema (theme.js)
5. MotionKit (MK) e MV — para custom.js
6. Comandos e flags

---

## 1. Projeto
```
work/<slug>/
├── index.html      composição (copiada de assets/engine/composition.html — não edite)
├── data.json       roteiro + timeline (fonte da verdade)
├── audio/          vo.wav (tts.py), final.wav (master_audio.py)
├── media/          imagens/vídeos de b-roll do usuário
├── sfx/            SFX próprios (substituem os procedurais pelo nome)
├── custom.js/.css  opcionais (via meta.js/meta.css)
├── build/          stills/, qa/, cues.json, meta.json, video.mp4
└── out/<slug>.mp4  ENTREGA
```
O renderizador serve o projeto em `/` e a skill em `/_mv/`.

## 2. data.json
```jsonc
{
  "meta": {
    "fps": 60, "width": 1080, "height": 1920, "slug": "meu-video",
    "mblur": 1,                       // motion blur padrão do projeto (1 = desligado)
    "css": ["/_mv/assets/fonts/extra/x.css", "custom.css"],
    "js": ["custom.js"]               // pode definir window.MV_CUSTOM = async (data, theme) => {...}
  },
  "style": "kinetic-impact",          // pasta em styles/
  "theme": { "colors": { "accent": "#00e5ff" } },   // overrides do tema (merge profundo)
  "captions": { "enabled": false, "emph": ["grátis"], "maxWords": 3 },
  "qa": { "whitelist": ["Novexa", "CapCut"] },     // nomes próprios/marcas para o corretor
  "music": "media/musica.mp3",        // opcional (ou --music no make.py / user_audio.py --mode music)
  "imageStyle": "cinematic photo, teal and orange, 35mm",   // estilo comum das imagens geradas
  "scenes": [
    {
      "type": "hook",                 // hook|text|quote|list|stat|cta|image|html|<custom>
      "show": "Seu vídeo *morre* em 3 segundos",   // texto NA TELA. *x* = destaque, _x_ = destaque 2, \n = quebra
      "say": "Seu vídeo morre em três segundos.",  // texto FALADO (TTS). Sem say → usa dur ou tempo de leitura
      "kicker": "DICA RÁPIDA",        // rótulo pequeno acima (opcional)
      "enter": "slam", "exit": "zoom", "transition": "punch", "highlight": "box",   // overrides por cena
      "sync": true,                   // palavra aparece quando é falada (padrão: true, exceto hook)
      "upper": true, "idle": 0.05, "hold": 0.3,      // hold = segura a cena +0.3 s
      "dur": 2.0,                     // só sem "say"
      "image": "media/foto.jpg",      // imagem/vídeo da cena (qualquer tipo de cena)
      "imageLayout": "cover",         // cover | card | float
      "image_prompt": "close-up of…", // gen_images.py gera e preenche "image"
      "seed": 7, "kenburns": "in", "imagePos": "50% 30%",
      "fit": { "max": 170, "min": 60, "maxLines": 4 },
      "start": 0, "end": 2.2, "words": []          // preenchidos pelo tts.py — não edite à mão
    }
  ]
  // "words", "audioDuration", "audio" são escritos pelo tts.py
}
```

## 3. Tipos de cena
| Tipo | Campos | Comportamento |
|---|---|---|
| `hook` | show, say, kicker | frase inteira entra em ~0,5 s; quadro 0 já legível |
| `text` | show, say, kicker | palavras sincronizadas com a voz |
| `quote` | show | citação (tema define blur/fade) |
| `list` | num ("#1", "01"), show | número grande + item |
| `stat` | value {to, from, decimals, prefix, suffix, dur, grouping} (grouping:false p/ anos), show (rótulo) | contagem animada + riser + impact + punch |
| `cta` | show | fechamento (não sai — segura até o fim) |
| `image` | src (jpg/png/mp4 em media/), offset, show | b-roll em tela cheia com Ken Burns; vídeo é sincronizado quadro a quadro |
| `html` | html (com `data-anim="pop"` nos filhos) | layout livre |
| custom | qualquer | registre em custom.js: `MV.sceneBuilders.meuTipo = (el, sc, theme, i) => {...}` |

## 4. Tema (`MV.registerTheme(nome, {...})`)
| Chave | Exemplo | Efeito |
|---|---|---|
| colors | {bg, bg2, text, accent, accent2, flash} | viram variáveis CSS `--bg`, `--accent`… |
| fonts | {display: "Anton", body: "Montserrat"} | `--font-display`, `--font-body` |
| upper | true | caixa alta (pt-BR correto: ç, ã…) |
| bg | {type: solid\|gradient\|mesh\|grid, c1, c2, blobs, alpha, size, speed, line, vignette} | fundo procedural |
| grain | 0.08 | grão de filme (aplicado no encode) |
| particles | {count, color, speed, size, seed} | partículas determinísticas |
| progress | true | barra de progresso no topo |
| enter | {hook, text, list, stat, quote, cta, default} | presets: slam pop rise blur drop flip stretch wipe type fade scramble |
| exit | "zoom" | up down zoom shrink blur fade left cut |
| hookTransition / transitions / transition | "punch" / ["punch","whip"] | punch whip shake flash glitch zoom none |
| highlight | "box" | color box marker |
| shakeOnEmphasis | true | micro-shake nos destaques |
| idle | 0.05 | zoom contínuo por cena (0 desliga) |
| stagger | 0.07 | atraso entre palavras sem sync |
| sync / syncHook | true / false | sincronia texto-voz |
| chars | false | dividir em letras (necessário p/ animações por letra em custom) |
| fit / fitByType | {max, min, maxLines} | auto-ajuste de tamanho |
| sfx | {transition, emphasis, impact, stat, glitch, type, word, enter} | nomes da biblioteca de SFX |
| captions | {maxWords, maxChars, upper, pop} | legenda karaokê |
| custom | true | carrega `styles/<nome>/custom.js` |

## 5. MK / MV (custom.js)
```js
// posicionar tweens no tempo absoluto (s)
MV.tl.fromTo("#s2 .mk-text", {rotation: -8}, {rotation: 0, duration: .5, ease: "back.out(2)"}, 4.2);
MV.cue(4.2, "whoosh", 0.8);                 // SFX no quadro exato
MK.shake(5.0, {dur: .3, amp: 20});          // câmera
MK.punch(5.0, 0.12); MK.flash(6.1, "#fff"); MK.glitchHit(7.0);
MK.counter(el, t0, dur, {to: 1500, prefix: "R$ ", decimals: 0});
MK.scramble(el, "TEXTO", t0, 0.8);
MK.track(t0, dur, (p, t) => { el.style.setProperty("--p", p); });   // efeito procedural
MV.onFrame(t => { /* qualquer coisa função de t */ });
const r = MK.rng(42); MK.noise(t * 2, 7);   // aleatoriedade determinística
MK.splitText(el, "Texto *destacado*", {upper: true, chars: true}); MK.fit(el, {max: 160});
MK.enter.meuPreset = (t, o = {}) => gsap.timeline().from(t, {...});  // novo preset de entrada
window.MV_CUSTOM = async (data, theme) => { /* roda depois de montar as cenas */ };
```
Camadas do DOM: `#bg` → `#particles` → `#camera` (shake) → `#zoom` (punch/whip) → `#content` (cenas) →
`#captions` → `#glitch` → `#flash` → `#grain` → `#progress`.

## 6. Comandos
| Comando | Para quê |
|---|---|
| `python scripts/new_project.py work/x --style S` / `--list` | criar projeto / listar estilos |
| `python scripts/make.py work/x [--music m.mp3 --beats] [--mblur 4] [--draft] [--no-final]` | pipeline completo |
| `python scripts/tts.py work/x --engine auto --voice pt-BR-FranciscaNeural --rate +10%` | só voz/timeline |
| `node scripts/render.mjs work/x --preflight-only` | checar fontes/glifos/layout + gerar cues |
| `node scripts/render.mjs work/x --stills 0,1.5,3 --safe` | quadros específicos para revisar |
| `node scripts/render.mjs work/x --review` | stills automáticos + contact sheet |
| `node scripts/render.mjs work/x [--draft] [--mblur 4] [--workers 4] [--crf 14]` | render |
| `python scripts/master_audio.py work/x --music m.mp3 --music-db -16` | só áudio |
| `python scripts/user_audio.py work/x voz.mp3 [--denoise] [--raw]` | narração enviada pelo usuário |
| `python scripts/user_audio.py work/x musica.mp3 --mode music` | música enviada pelo usuário (+ beats) |
| `python scripts/gen_images.py work/x [--provider pexels] [--only 2 --force]` | gerar imagens das cenas |
| `python scripts/qa.py work/x` | QA final |
| `python scripts/beats.py m.mp3 --out work/x/build/beats.json` | BPM/batidas |
| `python scripts/analyze_reference.py ref.mp4 --out refs/nome [--compare out.mp4]` | dissecar referência |
| `python scripts/fetch_font.py "Nome"` | baixar Google Font |
| `python scripts/sfx.py` | (re)gerar biblioteca de SFX |
| `node scripts/render.mjs work/x --serve` | preview ao vivo no navegador (máquina local) |
