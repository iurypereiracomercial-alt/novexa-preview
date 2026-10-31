/* GLITCH TECH — hacker/IA/tecnologia: grid, scanlines, texto embaralhando, cortes com glitch RGB. */
MV.registerTheme("glitch-tech", {
  colors: { bg: "#05070a", bg2: "#0b1220", text: "#e8fff4", accent: "#00ff88", accent2: "#ff2bd6", flash: "#00ff88" },
  fonts: { display: "Space Grotesk", body: "JetBrains Mono" },
  upper: true,
  bg: { type: "grid", line: "rgba(0,255,136,.09)", speed: 60 },
  grain: 0.06,
  progress: true,
  enter: { hook: "scramble", text: "scramble", list: "type", stat: "pop", quote: "type", cta: "scramble", default: "scramble" },
  exit: "cut",
  hookTransition: "glitch",
  transitions: ["glitch", "punch", "glitch", "whip"],
  highlight: "marker",
  idle: 0.03,
  sync: true,
  fit: { max: 150, min: 56, maxLines: 4 },
  sfx: { transition: "whoosh", emphasis: "glitch", impact: "bass", stat: "riser", glitch: "glitch", type: "click" },
  captions: { maxWords: 3, maxChars: 18, upper: true }
});
