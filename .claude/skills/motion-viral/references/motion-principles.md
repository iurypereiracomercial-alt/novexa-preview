# Princípios de Motion Design — fluidez, timing e tipografia profissional

## Índice
1. Fluidez (por que 60 fps determinístico)
2. Easing — a diferença entre amador e profissional
3. Tabela de tempos
4. Tipografia em movimento
5. Cor, contraste e textura
6. Câmera e transições
7. Regras de determinismo (para animações customizadas)
8. Erros que denunciam amadorismo

---

## 1. Fluidez
- O render é **quadro a quadro**: cada quadro é calculado no tempo exato `t = n/fps` e capturado sem perdas.
  Não existe "lag" nem quadro pulado, mesmo numa máquina lenta — a máquina lenta só demora mais.
- **60 fps** é o padrão (movimento rápido de texto fica nítido e suave). 30 fps só em rascunho (`--draft`).
- Motion blur opcional (`--mblur 4`): média de 4 subquadros com obturador de 180°. Deixa whips/slams cinematográficos;
  custa 4× o tempo. Use no render final de estilos com muito movimento rápido (kinetic-impact, glitch-tech).
- Anime **transform/opacity/filter**, nunca `top/left/width` (causa tremido por arredondamento de pixel).
- Texto em movimento lento sofre "stepping" se não estiver em camada composta: os elementos `.w` já têm
  `will-change: transform`.

## 2. Easing
Movimento natural acelera e desacelera. Linear só para movimento contínuo (scroll de grid, drift de fundo).

| Uso | Curva | Por quê |
|---|---|---|
| Entrada de texto | `expo.out` / `power4.out` | chega rápido e assenta suave — sensação de energia controlada |
| Pop / destaque | `back.out(2–2.6)` | overshoot leve dá "vida" |
| Saída | `power2.in` (0,2–0,3 s) | sai acelerando, rápido; saída nunca deve ser mais lenta que a entrada |
| Transição de cena | `expo.inOut` / `mv.whip` | whip pan com pico de velocidade no meio |
| Elegante/premium | `power3.out`, `mv.smooth` | sem overshoot |
| Contadores | ease-out quártico (já no `MK.counter`) | os números desaceleram ao chegar no valor final |

Curvas próprias registradas: `mv.snap`, `mv.smooth`, `mv.whip`, `mv.overshoot`.

## 3. Tabela de tempos (60 fps)
| Ação | Duração | Quadros |
|---|---|---|
| Slam/pop de palavra | 0,35–0,45 s | 21–27 |
| Rise com máscara | 0,5–0,65 s | 30–39 |
| Blur-in | 0,6–0,8 s | 36–48 |
| Stagger entre palavras (sem sync) | 0,05–0,09 s | 3–5 |
| Stagger entre letras | 0,02–0,04 s | 1–2 |
| Saída | 0,18–0,3 s | 11–18 |
| Zoom punch | 0,35–0,5 s, amplitude 6–14% | |
| Shake | 0,25–0,35 s, 10–22 px | |
| Flash | 0,15–0,2 s | |
| Leitura mínima de texto na tela | 0,45 s + 0,3 s/palavra | |

## 4. Tipografia em movimento
- Fontes **display condensadas e pesadas** (Anton, Bebas Neue, Montserrat 800–900, Archivo Black, Poppins Black)
  para kinetic; **Inter/Space Grotesk** para premium/tech; **DM Serif Display** para storytelling.
- CAIXA ALTA aumenta impacto e legibilidade em telas pequenas; minúsculas transmitem calma/premium.
- 1 família display + 1 de apoio, no máximo. Pesos: 800–900 para títulos.
- Entrelinha 0,95–1,05 em display; tracking levemente negativo em sans geométricas grandes.
- Acentos: o motor checa glifos (Ã, Ç, É…) e reserva folga na máscara para não cortá-los.
- `MK.fit` encontra o maior tamanho que cabe sem quebrar palavras, já descontando o micro-zoom e o pop.
- Bebas Neue não tem minúsculas: use só com `upper: true`.
- Fonte nova: `python scripts/fetch_font.py "Nome"` (Google Fonts, OFL) e adicione em `meta.css`.

## 5. Cor, contraste e textura
- Paleta: 1 fundo + 1 texto + 1 destaque (+ 1 secundário opcional). Destaque **saturado e quente** (amarelo, laranja,
  verde neon, rosa) sobre fundo escuro é o padrão de maior contraste.
- Contraste texto/fundo ≥ 7:1 para títulos. Sobre vídeo/imagem: contorno 10–14 px ou sombra forte.
- **Grão** (3–10%) mascara banding de gradiente e dá textura "filmada"; **vinheta** foca o centro.
- Fundo vivo: gradiente/mesh com movimento lento (via `MK.noise`) — nunca um fundo 100% estático.

## 6. Câmera e transições
- Hierarquia: `#camera` (shake) → `#zoom` (punch/whip/zoom) → `#content` (cenas). Animações de cena não brigam com a câmera.
- Transições disponíveis: `punch`, `whip`, `shake`, `flash`, `glitch`, `zoom`, `none`. Cada uma registra SFX automaticamente.
- Varie: o tema define um ciclo. 1 transição forte (flash/shake) a cada 2–3 cenas, não em todas.

## 7. Regras de determinismo (custom.js)
Tudo deve ser **função pura do tempo**:
- ✅ `MV.tl.to(el, {...}, t)` — tweens posicionados em segundos absolutos.
- ✅ `MV.onFrame(t => ...)` / `MK.track(t0, dur, (p, t) => ...)` — efeitos procedurais.
- ✅ `MK.rng(seed)`, `MK.noise(x, seed)` — aleatoriedade com semente.
- ❌ `Math.random()`, `Date.now()`, `setTimeout`, `setInterval`, `requestAnimationFrame` acumulando estado,
  CSS `transition` (animações CSS `@keyframes` são aceitas — o renderizador as controla pelo tempo).
- ❌ `tl.call()` com efeitos colaterais. Use `MV.tl.set()` para trocas de estado.
- Teste: `--stills` em tempos fora de ordem devem gerar imagens idênticas às do render.

## 8. Erros que denunciam amadorismo
- Fade-in do preto no início · texto pequeno · fonte padrão do sistema (fallback) · letras faltando acento
- Tudo entrando com a mesma animação · movimento linear · saída mais lenta que a entrada
- Tela parada · texto embaixo dos botões do TikTok · música mais alta que a voz · SFX em toda palavra
- Áudio estourado ou baixo demais · 24/30 fps com movimento rápido (stutter) · cores lavadas (sem BT.709)
