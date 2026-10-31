/* CAPTIONS POP — legendas palavra a palavra grandes, estilo "podcast cut" / talking head.
   Use sobre vídeo (cena type:image com src .mp4) ou fundo animado. Legenda faz a narrativa. */
MV.registerTheme("captions-pop", {
  colors: { bg: "#101014", bg2: "#22222c", text: "#ffffff", accent: "#ffe600", accent2: "#36ff6b", flash: "#ffffff" },
  fonts: { display: "Montserrat", body: "Montserrat" },
  upper: true,
  bg: { type: "gradient" },
  grain: 0.04,
  progress: false,
  enter: { hook: "pop", default: "pop" },
  exit: "shrink",
  hookTransition: "punch",
  transitions: ["punch", "none", "whip", "none"],
  highlight: "color",
  idle: 0.03,
  sync: true,
  fit: { max: 120, min: 56, maxLines: 3 },
  sfx: { transition: "swoosh", emphasis: "pop", impact: "bass", stat: "riser" },
  captions: { maxWords: 3, maxChars: 16, upper: true, pop: true }
});
