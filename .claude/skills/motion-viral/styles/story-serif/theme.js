/* STORY SERIF — storytelling/documentário: serifada elegante, tons quentes, revelações com wipe e marcador. */
MV.registerTheme("story-serif", {
  colors: { bg: "#14100c", bg2: "#2a1f16", text: "#f6efe4", accent: "#ff7a1a", accent2: "#ffd29a", flash: "#fff3e0" },
  fonts: { display: "DM Serif Display", body: "Inter" },
  upper: false,
  bg: { type: "mesh", blobs: ["#ff7a1a", "#8a3b12", "#ffd29a"], alpha: 0.16, size: 60 },
  grain: 0.1,
  progress: true,
  enter: { hook: "rise", text: "rise", list: "rise", stat: "fade", quote: "fade", cta: "rise", default: "rise" },
  exit: "fade",
  hookTransition: "zoom",
  transitions: ["zoom", "whip"],
  highlight: "marker",
  idle: 0.035,
  stagger: 0.08,
  sync: true,
  fit: { max: 150, min: 60, maxLines: 5 },
  sfx: { transition: "swoosh", emphasis: "tick", impact: "bass", stat: "riser" },
  captions: { maxWords: 4, maxChars: 22, upper: false }
});
