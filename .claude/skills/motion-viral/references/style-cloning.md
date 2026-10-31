# Clonar um estilo a partir de uma referência

Quando o usuário mandar um vídeo (arquivo ou link) e disser "quero nesse estilo", reproduza a **linguagem visual e
sonora** (tipografia, cores, ritmo, animações, transições, SFX) com conteúdo novo. Não copie trechos, marcas,
logotipos, personagens ou a voz de pessoas reais — o objetivo é o *estilo*, não o vídeo.

## Passo a passo
1. **Dissecar**
   ```bash
   python scripts/analyze_reference.py ref.mp4 --out refs/<nome-do-estilo>
   ```
   Abra (Read) `hook_strip.png`, `keyframes.png`, `cut_frames/*.png`, `motion.png`, `palette.png` e `info.json`.
2. **Preencher `STYLE_SPEC.md`** respondendo cada item olhando as imagens:
   - Conte quadros no `hook_strip` (10 fps → cada quadro = 0,1 s) para medir a duração das entradas.
   - Identifique a fonte: compare formas de letras-chave (R, G, a, e, M). Escolha a mais próxima no Google Fonts
     (condensada pesada → Anton/Bebas/Oswald; geométrica → Montserrat/Poppins; grotesca → Inter/Archivo; serifa
     → DM Serif/Playfair). Baixe com `scripts/fetch_font.py`.
   - Cores: use `palette` do info.json + conta-gotas visual nos cut_frames.
   - Ritmo: `avg_shot_s` e `cuts_per_10s` → duração média das cenas; `still_ratio` alto = estilo calmo.
   - Áudio: BPM, se há voz, quais SFX se ouvem.
3. **Criar o estilo** em `styles/<nome>/`:
   - `theme.js` — copie o tema mais próximo e ajuste `colors`, `fonts`, `upper`, `enter`, `exit`, `transitions`,
     `highlight`, `idle`, `grain`, `bg`, `sfx`, `captions`, `fit`.
   - `theme.css` — detalhes visuais (contorno, sombra, tracking, posição, scanlines…), sempre prefixados com `.style-<nome>`.
   - `style.md` — ficha igual às dos outros estilos (quando usar, fontes, paleta, entradas, transições, SFX).
   - Animação que não existe nos presets → crie em `styles/<nome>/custom.js` registrando um preset novo
     (`MK.enter.meuPreset = (t, o) => gsap.timeline().from(...)`) e carregue via `data.meta.js`.
     Siga as regras de determinismo de `motion-principles.md`.
4. **Testar e comparar**
   ```bash
   python scripts/new_project.py work/teste-<nome> --style <nome>
   python scripts/make.py work/teste-<nome>
   python scripts/analyze_reference.py ref.mp4 --out refs/<nome> --compare work/teste-<nome>/out/teste-<nome>.mp4
   ```
   Abra `compare.png` (cima = referência, baixo = nosso). Ajuste até ficar indistinguível em: tamanho e peso da
   fonte, posição vertical, cor do destaque, velocidade das entradas, tipo de transição, densidade de texto.
5. **Registrar**: o estilo fica disponível para sempre (`new_project.py --list`). Diga ao usuário o nome para pedir
   "faz um vídeo no estilo <nome>".

## Mapa rápido "o que vejo" → "o que configuro"
| Na referência | Configuração |
|---|---|
| Palavra cai grande e encolhe batendo | `enter: slam` |
| Palavra salta com elasticidade | `enter: pop` |
| Palavra sobe de dentro de uma linha invisível | `enter: rise` |
| Texto surge desfocado e fica nítido | `enter: blur` |
| Letras embaralhadas viram a palavra | `enter: scramble` |
| Máquina de escrever | `enter: type` |
| Texto revelado por uma cortina lateral | `enter: wipe` |
| Palavra com fundo colorido | `highlight: box` |
| Faixa de marca-texto passando | `highlight: marker` |
| Só muda a cor | `highlight: color` |
| Tela treme no golpe | `shakeOnEmphasis: true`, transição `shake` |
| Zoom rápido no corte | transição `punch` |
| Clarão branco no corte | transição `flash` |
| Deslize com borrão lateral | transição `whip` |
| Faixa RGB tremida | transição `glitch` |
| Legenda palavra a palavra embaixo | `captions.enabled: true` (tema captions-pop) |
| Barra no topo enchendo | `progress: true` |
| Textura granulada | `grain: 0.05–0.12` |
