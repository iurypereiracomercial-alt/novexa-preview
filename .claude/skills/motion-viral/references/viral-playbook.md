# Viral Playbook — ganchos, retenção e estrutura de motion para TikTok/Reels/Shorts

Leia antes de escrever o roteiro. Os números abaixo vêm de guias de mercado (Opus Clip, TikTok for Business,
blogs de criadores, out/2026) e são **direcionais**, não leis — a verdade é a curva de retenção do próprio perfil.

## Índice
1. A física da retenção
2. Os primeiros 3 segundos (gancho)
3. Biblioteca de ganchos (PT-BR, com fórmula)
4. Estrutura do vídeo (beat sheet)
5. Pattern interrupts e ritmo
6. Final em loop e CTA
7. Texto na tela e assistir sem som
8. Duração, especificações e publicação
9. Checklist de roteiro

---

## 1. A física da retenção
- O algoritmo distribui pelo **% assistido + replays + compartilhamentos/salvamentos**. Motion design ajuda em tudo isso
  porque a tela nunca "morre": sempre há algo entrando, mudando ou se movendo.
- A decisão de ficar acontece em **1–3 s** e é quase instintiva. O vídeo precisa entregar *por que assistir* antes do
  dedo rolar.
- Depois do gancho, a ameaça é a **monotonia**: um novo estímulo a cada **2–4 s** (corte, zoom punch, palavra destacada,
  número subindo, SFX) mantém o cérebro em modo de "o que vem agora".
- Tela parada > 1,2 s = queda de retenção. O motor aplica micro-zoom contínuo (`idle`) e o QA acusa congelamentos.

## 2. Os primeiros 3 segundos
Regras que o motor já aplica ou que você deve garantir no roteiro:
1. **Quadro 0 legível.** Nada de fade do preto, logo, "oi gente". O 1º quadro vira a capa no feed. (O motor deixa a
   primeira palavra pré-animada e bloqueia flash/glitch no quadro 0.)
2. **Texto do gancho na tela em ≤ 0,5 s** e por ≥ 2 s — muita gente assiste sem som. Cena `hook` mostra a frase inteira
   rápido (não espera a voz).
3. **Voz começa no quadro 0** (o `tts.py` remove o silêncio inicial).
4. **Golpe sonoro no início** (impact/bass/whoosh) — sinal de "algo aconteceu".
5. **Promessa específica** com número, prazo, dor ou contradição. "3 erros que matam seu vídeo" > "dicas de vídeo".
6. **Abrir um loop** (pergunta não respondida) que só fecha no fim → segura até o final.
7. Gancho curto: 5–9 palavras na tela, ≤ 2 linhas de voz.

## 3. Biblioteca de ganchos (fórmula → exemplo)
Escolha 1 tipo, escreva 3 variações e fique com a mais específica.

| Tipo | Fórmula | Exemplo |
|---|---|---|
| Dor direta | Seu [coisa] [problema grave] por causa de [causa] | "Seu vídeo morre em 3 segundos por causa disso" |
| Erro/aviso | Pare de [hábito comum] | "Pare de começar vídeo com 'oi gente'" |
| Número + promessa | [N] [coisas] que [resultado] em [prazo] | "3 truques que dobram sua retenção hoje" |
| Resultado primeiro | Isso fez [resultado concreto] — e levou [tempo curto] | "Esse vídeo de 20 s teve 2 milhões de views" |
| Contradição | Todo mundo diz [crença]. Está errado. | "Todo mundo diz pra postar todo dia. Está errado." |
| Segredo/bastidor | O que [grupo] não te conta sobre [tema] | "O que os editores grandes não te contam" |
| Curiosidade numérica | [Estatística chocante] | "71% das pessoas decidem em menos de 3 segundos" |
| POV / identificação | POV: você [situação comum frustrante] | "POV: você editou 5 horas e teve 200 views" |
| Desafio | Aposto que você não sabia [fato] | "Aposto que você não sabia disso sobre o Excel" |
| Comparação | [A] vs [B]: qual [critério]? | "Celular de R$ 1.000 vs R$ 10.000 na câmera" |
| Antes/depois | De [estado ruim] para [estado bom] em [prazo] | "De 0 a 10 mil seguidores em 30 dias" |
| Pergunta fechada | Você sabe por que [fenômeno]? | "Você sabe por que o avião não voa em linha reta?" |
| Lista com recompensa | O [último item] é o mais importante | "Dica 3 é a que ninguém usa" |
| Urgência | Se você [faz X], assiste até o fim | "Se você vende online, assiste até o fim" |

Gatilhos de palavra que costumam funcionar no gancho: *ninguém, segredo, erro, pare, nunca, só, em X segundos,
de graça, proibido, finalmente, a verdade*. Use com honestidade — gancho que não é pago pelo conteúdo gera
abandono e derruba a distribuição.

## 4. Estrutura (beat sheet) para 15–35 s
| Tempo | Bloco | O que acontece | Tipos de cena |
|---|---|---|---|
| 0–2,5 s | Gancho | promessa + loop aberto, golpe sonoro | `hook` |
| 2,5–5 s | Contexto/stakes | por que importa (1 frase) | `text`, `stat` |
| 5–25 s | Entrega | 2–5 pontos, um por cena, cada um com destaque | `list`, `text`, `stat`, `image` |
| a cada 3–6 s | Re-gancho | "mas o pior é o número 3…", "e isso muda tudo" | `text` curto |
| final 2–4 s | Payoff + CTA/loop | fecha o loop; CTA de salvar/seguir; frase que emenda no início | `cta` |

Regras: **1 ideia por cena**, 3–8 palavras na tela, cenas de 1,2–3 s. Corte tudo que não serve ao payoff.

## 5. Pattern interrupts e ritmo
- Alterne transições (o tema faz ciclo: punch → whip → shake → glitch). Repetir a mesma transição vira ruído.
- Destaque **1 palavra-chave por cena** (`*palavra*` no `show`) → caixa/cor + pop + SFX.
- Números: use cena `stat` (contagem + riser + impact) — números animados retêm muito.
- Varie a escala: uma cena com 1 palavra gigante depois de uma com 6 palavras quebra o padrão.
- Em vídeos com música: corte no beat (`make.py --music x.mp3 --beats`).
- Fala rápida e sem respiro morto: `--rate +8%` a `+15%` (edge) ou `--speed 1.08–1.15` (kokoro).

## 6. Final em loop e CTA
- **Loop:** a última frase deve emendar na primeira ("…e é por isso que" → volta pro gancho "seu vídeo morre em 3 s").
  Replays contam como retenção > 100%.
- CTA específico e de baixo atrito: "Salva pra não esquecer", "Manda pra quem precisa", "Parte 2 no perfil".
- Não peça follow no começo. Não termine com tela preta/logo longo (o motor não faz fade-out final).

## 7. Texto na tela (sound-off)
- Grande o suficiente: título ≥ 7% da largura (≈ 75 px em 1080), legenda ≥ 80 px.
- Contraste máximo: branco/amarelo sobre escuro, com contorno ou sombra quando houver imagem de fundo.
- Dentro da **safe zone** (1080x1920): topo 250 px, base 560 px, esquerda 90 px, direita 140 px livres
  (UI do TikTok: perfil, legenda, botões). O preflight avisa quando algo fica fora.
- Nunca quebre palavra no meio; prefira linhas equilibradas (`text-wrap: balance` já ativo).
- Ortografia perfeita: erro de português derruba credibilidade e gera comentário negativo. O QA checa acentuação.

## 8. Duração, specs e publicação
- Duração-alvo: **15–35 s** para conteúdo informativo; até 60 s se cada bloco tiver re-gancho.
- Exportação do motor: 1080x1920, H.264 High, yuv420p BT.709, **60 fps constantes**, AAC 320 kbps 48 kHz,
  -14 LUFS, true peak ≤ -1 dBTP, `+faststart`.
- TikTok/Instagram re-encodam; subir em alta qualidade minimiza perdas. No TikTok, ative "Permitir upload em alta
  qualidade" nas configurações.
- Música: em perfis **comerciais/marca**, use só a Commercial Music Library da plataforma ou música royalty-free.
  Sons em alta do app podem ser adicionados na própria plataforma (com o volume da trilha original baixo).
- Legenda do post: repita a promessa do gancho + 3–5 hashtags específicas do nicho.

## 9. Checklist de roteiro (antes de renderizar)
- [ ] O gancho tem número/dor/contradição específica e cabe em 2 linhas?
- [ ] O quadro 0 já comunica o tema sem som?
- [ ] Há um loop aberto que só fecha no final?
- [ ] Cada cena tem 1 ideia e 1 palavra destacada?
- [ ] Algo muda na tela a cada ≤ 3 s?
- [ ] O final emenda no começo (loop) e tem CTA de baixo atrito?
- [ ] Duração total 15–35 s?
