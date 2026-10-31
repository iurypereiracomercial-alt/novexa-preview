/* KINETIC IMPACT — tipografia cinética pesada, fundo escuro, destaque amarelo.
   O formato "faceless" mais viral: frases curtas batendo na tela no ritmo da voz. */
MV.registerTheme("kinetic-impact", {
  colors: { bg: "#0a0a0c", bg2: "#17171f", text: "#ffffff", accent: "#ffd60a", accent2: "#ff3b5c", flash: "#ffffff" },
  fonts: { display: "Anton", body: "Montserrat" },
  upper: true,
  bg: { type: "mesh", blobs: ["#ffd60a", "#ff3b5c", "#3a3aff"], alpha: "22", size: 55 },
  grain: 0.08,
  progress: true,
  enter: { hook: "slam", text: "pop", list: "rise", quote: "blur", cta: "slam", default: "pop" },
  exit: "zoom",
  hookTransition: "punch",
  transitions: ["punch", "whip", "shake", "punch", "glitch"],
  highlight: "box",
  shakeOnEmphasis: true,
  idle: 0.05,
  sync: true,
  fit: { max: 190, min: 70, maxLines: 4 },
  fitByType: { quote: { max: 120, maxLines: 6 } },
  sfx: { transition: "whoosh", emphasis: "pop", impact: "impact", stat: "riser", glitch: "glitch", type: "click" },
  captions: { maxWords: 3, maxChars: 16, upper: true }
});
