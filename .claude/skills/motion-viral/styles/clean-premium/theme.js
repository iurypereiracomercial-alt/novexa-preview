/* CLEAN PREMIUM — minimalista, elegante, movimentos suaves com blur (estética de keynote/produto). */
MV.registerTheme("clean-premium", {
  colors: { bg: "#f5f5f7", bg2: "#e8e8ed", text: "#111114", accent: "#0a66ff", accent2: "#7a3cff", flash: "#ffffff" },
  fonts: { display: "Inter", body: "Inter" },
  upper: false,
  bg: { type: "mesh", blobs: ["#0a66ff", "#7a3cff", "#00c2ff"], alpha: 0.10, size: 60, vignette: false },
  grain: 0.025,
  progress: false,
  enter: { hook: "blur", text: "blur", list: "rise", stat: "blur", quote: "blur", cta: "rise", default: "blur" },
  exit: "blur",
  hookTransition: "zoom",
  transitions: ["zoom"],
  highlight: "color",
  idle: 0.025,
  stagger: 0.09,
  sync: true,
  fit: { max: 150, min: 56, maxLines: 4 },
  sfx: { transition: "swoosh", emphasis: "tick", impact: "ding", stat: "riser", word: null },
  captions: { maxWords: 4, maxChars: 22, upper: false }
});
