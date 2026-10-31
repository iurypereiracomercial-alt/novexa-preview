# Imagens e áudio: do usuário ou gerados pela skill

Leia depois das perguntas do passo 0. Cada caminho tem requisitos próprios de qualidade.

## Índice
1. Imagens enviadas pelo usuário
2. Imagens geradas pela skill
3. Layouts de imagem nas cenas
4. Narração enviada pelo usuário
5. Música enviada pelo usuário
6. Combinações comuns

---

## 1. Imagens enviadas pelo usuário
- Peça os arquivos e diga o que precisa: **vertical 9:16, no mínimo 1080x1920** para fundo; quadrada ≥ 1080 px para
  card; **PNG com fundo transparente** para produto ou pessoa recortada (`float`); vídeos de b-roll em MP4.
- Copie para `work/<slug>/media/` com nomes simples, sem espaços nem acentos (`produto-1.png`).
- Abra cada imagem com Read antes de usar: confira assunto, qualidade, marca d'água e texto embutido que possa
  conflitar com o texto animado.
- O preflight acusa imagem que não carregou (erro) e imagem ampliada mais de 1,35× (aviso de baixa resolução).
  Em baixa resolução, troque o layout para `card` (menor na tela) ou peça um arquivo maior.
- Ajuste o enquadramento com `"imagePos": "50% 30%"` (equivale a object-position) quando o assunto ficar cortado.

## 2. Imagens geradas pela skill
```bash
python SKILL_DIR/scripts/gen_images.py work/<slug>          # ou make.py --gen-images
```
- Provedores grátis: **Pollinations** (IA FLUX, sem cadastro) e, como alternativa, **Pexels** (fotos reais de banco;
  chave grátis em `PEXELS_API_KEY`). Se a sessão tiver outras ferramentas de geração de imagem conectadas, elas podem
  ser usadas, mas costumam gastar créditos: **pergunte antes** e salve o resultado como `media/sNN.jpg`.
- Escreva `image_prompt` **em inglês** (os modelos entendem melhor), concreto e visual:
  *assunto + ação + cenário + luz + enquadramento*. Ex.: "close-up of a hand holding a smartphone showing a
  rising chart, dark desk, neon blue rim light, shallow depth of field".
- Use `"imageStyle"` no topo do data.json para manter a mesma estética em todas as cenas (ex.: "cinematic photo,
  teal and orange grade, 35mm, high detail").
- O script já acrescenta "no text, no letters, no watermark". **Nunca** peça texto dentro da imagem: o texto é sempre
  animado pela skill, e a IA erra letras.
- **Revisão obrigatória** de `build/images_sheet.png`: mãos/rostos deformados, objetos derretidos, texto falso,
  marca d'água, coerência entre as cenas. Para refazer uma cena, mude o `"seed"` dela e rode
  `gen_images.py work/<slug> --only <índice> --force`.
- Não gere imagens de pessoas reais identificáveis nem de marcas e logotipos de terceiros.

## 3. Layouts de imagem
Qualquer cena pode ter `"image"` (ou `"src"` na cena `image`):

| `imageLayout` | Visual | Texto | Bom para |
|---|---|---|---|
| `cover` (padrão) | tela cheia + Ken Burns + sombreado | por cima, centralizado | b-roll, atmosfera, storytelling |
| `card` | cartão arredondado no topo (entra com pop) | abaixo do card | prints, produtos, antes/depois, provas |
| `float` | PNG recortado flutuando com sombra | abaixo | produto, personagem, objeto |

Opções extras: `"kenburns": "in|out|left|right|none"`, `"imagePos"`, `"offset"` (início do vídeo de b-roll, em s).

## 4. Narração enviada pelo usuário
```bash
python SKILL_DIR/scripts/user_audio.py work/<slug> media/narracao.mp3 [--denoise] [--raw]   # ou make.py --voice-file
```
- Formatos: MP3, WAV, M4A, OGG, ou até o áudio de um vídeo (MP4/MOV).
- **Transcrição primeiro:** sempre peça ao usuário o texto exato do áudio (passo 0.1 do SKILL.md) e passe com
  `--transcript work/<slug>/transcricao.txt`. Com ela, o script monta as cenas sozinho (`showDraft: true`) e você só
  reescreve os `show`. Sem `--transcript`, o script lê `transcricao.txt` do projeto, se estiver preenchido.
- **Conferência:** com Whisper disponível, o script imprime "conferência transcrição x áudio: NN%". Abaixo de 90%,
  a transcrição provavelmente não corresponde ao áudio (outra versão do texto, trecho faltando): confirme com o usuário.
- **Sincronia:**
  - Com Whisper instalado (`pip install faster-whisper`), usa os tempos reais de cada palavra.
  - Sem faster-whisper, tenta o **sherpa-onnx** (`pip install sherpa-onnx`; o modelo Whisper ~640 MB baixa do GitHub
    uma única vez e funciona mesmo em redes restritas). Ele transcreve cada trecho entre pausas e liga as palavras da
    transcrição a esses trechos (precisão de ~0,1 s).
  - Sem Whisper, usa o `say` de cada cena (o texto exato falado) e alinha os fins de frase às pausas da gravação.
    Peça o roteiro ao usuário, ou transcreva você mesmo ouvindo trechos curtos se ele não tiver.
- O silêncio do início é removido, para a voz entrar no quadro 0.
- Gravação caseira com chiado: `--denoise`. Áudio que já vem mixado ou masterizado (com música): `--raw`, para não
  aplicar a cadeia de voz.
- Confira o resultado nos stills: a palavra destacada deve aparecer quando é falada. Se uma cena começar adiantada,
  ajuste a pontuação do `say` (vírgulas e pontos marcam as pausas).

## 5. Música enviada pelo usuário
```bash
python SKILL_DIR/scripts/user_audio.py work/<slug> media/musica.mp3 --mode music [--offset 12.5]
python SKILL_DIR/scripts/tts.py work/<slug> --engine none --beats work/<slug>/build/beats.json   # só música
# ou com voz IA: --engine auto --beats ...
```
- Detecta BPM e batidas; os fins de cena caem no beat. `--offset` pula a introdução (comece no drop).
- Sem voz, a música fica em destaque (cerca de -6 dB). Com voz, fica em -16 dB e abaixa quando há fala (ducking).
- Lembre o usuário de ter direito de uso da música (royalty-free ou biblioteca comercial, em perfis de marca).

## 6. Combinações comuns
| Pedido | Comando |
|---|---|
| Tudo pela skill (voz IA + imagens IA) | `make.py work/x --gen-images` |
| Voz do usuário + só tipografia | `make.py work/x --voice-file media/voz.mp3` |
| Voz do usuário + imagens do usuário | imagens em `media/` + `"image"` nas cenas → `make.py work/x --voice-file media/voz.mp3` |
| Música do usuário, sem voz, cortes no beat | `user_audio.py work/x media/m.mp3 --mode music` → `tts.py work/x --engine none --beats work/x/build/beats.json` → `make.py work/x --skip-tts` |
| Voz IA + música do usuário | `make.py work/x --music media/m.mp3 --beats` |
