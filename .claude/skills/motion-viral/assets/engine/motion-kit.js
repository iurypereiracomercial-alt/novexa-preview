/* =====================================================================
   MOTION-KIT — núcleo determinístico de motion design (GSAP)
   ---------------------------------------------------------------------
   REGRA DE OURO: tudo que aparece na tela tem que ser função PURA do
   tempo t. Nada de Math.random() sem seed, setTimeout, setInterval ou
   requestAnimationFrame acumulando estado. Assim o render quadro-a-quadro
   é idêntico em qualquer máquina e o vídeo sai 100% fluido (60 fps reais,
   sem frame perdido).
   - Animações: MV.tl (timeline GSAP pausada, posicionada em segundos)
   - Efeitos procedurais (shake, grain, partículas, contadores):
     MV.onFrame(fn(t))  ou  MK.track(t0, dur, fn(p, t))
   - Efeitos sonoros sincronizados: MV.cue(t, "whoosh", ganho)
   ===================================================================== */
(function () {
  "use strict";
  const MV = (window.MV = window.MV || {});
  const MK = (window.MK = window.MK || {});

  MV.fps = 60; MV.width = 1080; MV.height = 1920; MV.duration = 0;
  MV.frameFns = []; MV.cues = []; MV.warnings = [];
  MV.themes = MV.themes || {};
  MV.tl = gsap.timeline({ paused: true });
  gsap.defaults({ ease: "expo.out", duration: 0.5 });
  gsap.config({ force3D: true, nullTargetWarn: false });
  if (window.CustomEase) {
    gsap.registerPlugin(CustomEase);
    // Curvas "assinatura" de motion profissional
    CustomEase.create("mv.snap", "M0,0 C0.12,0.9 0.2,1 1,1");          // entrada explosiva, assenta suave
    CustomEase.create("mv.smooth", "M0,0 C0.65,0 0.35,1 1,1");          // in-out elegante (estilo premium)
    CustomEase.create("mv.whip", "M0,0 C0.7,0 0.2,1 1,1");              // whip pan
    CustomEase.create("mv.overshoot", "M0,0 C0.18,1.35 0.4,1 1,1");     // passa do ponto e volta
  }

  MV.onFrame = (fn) => MV.frameFns.push(fn);
  MV.cue = (t, sfx, gain = 1) => { if (sfx) MV.cues.push({ t: Math.max(0, +(+t).toFixed(3)), sfx, gain }); };
  MV.warn = (msg) => { MV.warnings.push(msg); console.warn("[MV]", msg); };
  MV.registerTheme = (name, theme) => { MV.themes[name] = theme; };

  /* ---------------- aleatoriedade determinística ---------------- */
  MK.rng = function (seed) { // mulberry32
    let a = (seed >>> 0) || 1;
    return function () { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  };
  MK.hash = (n) => { const r = MK.rng((n * 2654435761) >>> 0); r(); return r(); };
  MK.noise = function (x, seed = 0) { // value noise 1D suave, saída em [-1, 1]
    const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f);
    const a = MK.hash(i + seed * 1013), b = MK.hash(i + 1 + seed * 1013);
    return (a + (b - a) * u) * 2 - 1;
  };
  MK.clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  MK.track = (t0, dur, fn) => MV.onFrame((t) => fn(MK.clamp((t - t0) / Math.max(dur, 1e-6)), t));

  /* ---------------- texto ---------------- */
  // Converte "Texto com *destaque* e _destaque2_\nnova linha" em spans palavra/letra.
  MK.esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  MK.tokens = function (text) {
    const out = []; let mode = null;
    String(text).split(/(\n)/).forEach((part) => {
      if (part === "\n") { out.push({ br: true }); return; }
      part.split(/\s+/).filter(Boolean).forEach((raw) => {
        let w = raw, hl = mode;
        if (/^[*_]/.test(w)) { mode = w[0] === "*" ? "hl" : "hl2"; hl = mode; w = w.slice(1); }
        const closes = /[*_]([.,!?;:…"')\]]*)$/.test(w);
        if (closes) { w = w.replace(/[*_]([.,!?;:…"')\]]*)$/, "$1"); hl = mode; mode = null; }
        out.push({ w, hl });
      });
    });
    return out;
  };
  MK.splitText = function (el, text, opts = {}) {
    const toks = MK.tokens(text); const words = [], chars = [];
    el.innerHTML = ""; el.classList.add("mk-text");
    toks.forEach((tk, i) => {
      if (tk.br) { el.appendChild(document.createElement("br")); return; }
      const w = document.createElement("span"); w.className = "w" + (tk.hl ? " " + tk.hl : "");
      const wi = document.createElement("span"); wi.className = "wi";
      const shown = opts.upper ? tk.w.toLocaleUpperCase("pt-BR") : tk.w;
      if (opts.chars) {
        Array.from(shown).forEach((ch) => { const c = document.createElement("span"); c.className = "c"; c.textContent = ch; wi.appendChild(c); chars.push(c); });
      } else wi.textContent = shown;
      w.dataset.word = tk.w; w.appendChild(wi); el.appendChild(w); words.push(w);
      const next = toks[i + 1]; if (next && !next.br) el.appendChild(document.createTextNode(" "));
    });
    return { words, chars, inners: words.map((w) => w.firstChild) };
  };
  // Auto-ajuste: maior fonte possível sem quebrar palavra no meio e sem estourar linhas/caixa.
  MK.fit = function (el, { max = 160, min = 40, maxLines = 4, width = null, height = null } = {}) {
    const box = el.parentElement; const W = width || el.clientWidth || box.clientWidth; const H = height || 99999;
    if (width) { el.style.width = W + "px"; el.style.maxWidth = "100%"; }
    let lo = min, hi = max, best = min;
    const fits = (s) => {
      el.style.fontSize = s + "px";
      const ws = el.querySelectorAll(".w"); let lines = new Set(), wide = false;
      ws.forEach((w) => { lines.add(Math.round(w.offsetTop)); if (w.offsetWidth > W + 1) wide = true; });
      return !wide && el.scrollWidth <= W + 1 && lines.size <= maxLines && el.scrollHeight <= H + 1;
    };
    for (let k = 0; k < 14; k++) { const mid = (lo + hi) / 2; if (fits(mid)) { best = mid; lo = mid; } else hi = mid; }
    el.style.fontSize = Math.floor(best) + "px";
    if (!fits(Math.floor(best))) MV.warn(`Texto não coube nem com ${min}px: "${el.textContent.slice(0, 40)}"`);
    return Math.floor(best);
  };

  /* ---------------- presets de entrada / saída ----------------
     Cada preset devolve uma timeline que você posiciona com MV.tl.add(tl, t). */
  const st = (o, d) => (o.stagger != null ? o.stagger : d);
  MK.enter = {
    slam: (t, o = {}) => gsap.timeline().from(t, { scale: o.scale || 2.4, autoAlpha: 0, duration: o.dur || 0.38, ease: "expo.out", stagger: st(o, 0.07), transformOrigin: "50% 60%" }),
    pop: (t, o = {}) => gsap.timeline().from(t, { scale: 0.3, autoAlpha: 0, y: 30, duration: o.dur || 0.42, ease: "back.out(2.4)", stagger: st(o, 0.06) }),
    rise: (t, o = {}) => gsap.timeline().from(t, { yPercent: 115, duration: o.dur || 0.6, ease: "expo.out", stagger: st(o, 0.06) }), // alvo = .wi (máscara no .w)
    blur: (t, o = {}) => gsap.timeline().from(t, { filter: "blur(28px)", autoAlpha: 0, scale: 1.12, duration: o.dur || 0.7, ease: "power3.out", stagger: st(o, 0.05) }),
    drop: (t, o = {}) => gsap.timeline().from(t, { y: -260, autoAlpha: 0, duration: o.dur || 0.55, ease: "back.out(1.8)", stagger: st(o, 0.06) }),
    flip: (t, o = {}) => gsap.timeline().from(t, { rotationX: -95, autoAlpha: 0, transformOrigin: "50% 100% -40", duration: o.dur || 0.6, ease: "expo.out", stagger: st(o, 0.05) }),
    stretch: (t, o = {}) => gsap.timeline().from(t, { scaleY: 0, scaleX: 1.3, autoAlpha: 0, transformOrigin: "50% 100%", duration: o.dur || 0.45, ease: "mv.overshoot", stagger: st(o, 0.05) }),
    wipe: (t, o = {}) => gsap.timeline().fromTo(t, { clipPath: "inset(-20% 100% -20% 0%)" }, { clipPath: "inset(-20% -5% -20% 0%)", duration: o.dur || 0.6, ease: "expo.inOut", stagger: st(o, 0.08) }),
    type: (t, o = {}) => gsap.timeline().from(t, { autoAlpha: 0, duration: 0.001, stagger: st(o, 0.035), ease: "none" }), // alvo = .c (letras)
    fade: (t, o = {}) => gsap.timeline().from(t, { autoAlpha: 0, y: 24, duration: o.dur || 0.5, ease: "power3.out", stagger: st(o, 0.05) }),
    // letras embaralhando até formar a palavra (determinístico: seed = progresso)
    scramble: (t, o = {}) => {
      const els = gsap.utils.toArray(t); const tl = gsap.timeline();
      els.forEach((el, i) => {
        const final = el.textContent; const set = o.set || "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#%&@$";
        const px = { p: 0 }; const dur = o.dur || Math.min(0.7, 0.18 + final.length * 0.05);
        tl.from(el, { autoAlpha: 0, duration: 0.01 }, i * st(o, 0.05))
          .fromTo(px, { p: 0 }, { p: 1, duration: dur, ease: "none", immediateRender: false, onUpdate: () => {
            const r = MK.rng(Math.floor(px.p * 24) * 31 + i + 1); const n = Math.floor(px.p * final.length);
            el.textContent = Array.from(final).map((ch, k) => (k < n || ch === " " ? ch : set[Math.floor(r() * set.length)])).join("");
          }, onComplete: () => { el.textContent = final; } }, i * st(o, 0.05));
      });
      return tl;
    },
  };
  MK.exit = {
    up: (t, o = {}) => gsap.timeline().to(t, { y: -90, autoAlpha: 0, duration: o.dur || 0.22, ease: "power2.in", stagger: st(o, 0.015) }),
    down: (t, o = {}) => gsap.timeline().to(t, { y: 90, autoAlpha: 0, duration: o.dur || 0.22, ease: "power2.in", stagger: st(o, 0.015) }),
    zoom: (t, o = {}) => gsap.timeline().to(t, { scale: 1.5, autoAlpha: 0, filter: "blur(10px)", duration: o.dur || 0.22, ease: "power2.in" }),
    shrink: (t, o = {}) => gsap.timeline().to(t, { scale: 0.6, autoAlpha: 0, duration: o.dur || 0.2, ease: "power2.in" }),
    blur: (t, o = {}) => gsap.timeline().to(t, { filter: "blur(24px)", autoAlpha: 0, duration: o.dur || 0.3, ease: "power2.in" }),
    fade: (t, o = {}) => gsap.timeline().to(t, { autoAlpha: 0, duration: o.dur || 0.2, ease: "power1.in" }),
    left: (t, o = {}) => gsap.timeline().to(t, { x: -700, autoAlpha: 0, duration: o.dur || 0.25, ease: "mv.whip" }),
    cut: (t) => gsap.timeline().set(t, { autoAlpha: 0 }),
  };
  // Durações aproximadas das saídas (para encaixar antes do fim da cena)
  MK.exitDur = { up: 0.22, down: 0.22, zoom: 0.22, shrink: 0.2, blur: 0.3, fade: 0.2, left: 0.25, cut: 0 };

  /* ---------------- câmera: zoom punch, shake, transições ---------------- */
  MK.camera = { shakes: [] };
  MK.shake = (t0, { dur = 0.35, amp = 18, rot = 1.2, freq = 22, seed = 7 } = {}) => MK.camera.shakes.push({ t0, dur, amp, rot, freq, seed });
  MV.onFrame((t) => {
    const cam = document.getElementById("camera"); if (!cam) return;
    let x = 0, y = 0, r = 0;
    for (const s of MK.camera.shakes) {
      const p = (t - s.t0) / s.dur; if (p < 0 || p > 1) continue;
      const k = Math.pow(1 - p, 2);
      x += MK.noise(t * s.freq, s.seed) * s.amp * k; y += MK.noise(t * s.freq, s.seed + 1) * s.amp * k; r += MK.noise(t * s.freq, s.seed + 2) * s.rot * k;
    }
    cam.style.transform = `translate3d(${x.toFixed(2)}px, ${y.toFixed(2)}px, 0) rotate(${r.toFixed(3)}deg)`;
  });
  MK.punch = (t0, amt = 0.12, dur = 0.5) => {
    MV.tl.fromTo("#zoom", { scale: 1 + amt }, { scale: 1, duration: dur, ease: "expo.out", immediateRender: false }, t0);
  };
  MK.flash = (t0, color = "#fff", peak = 0.85, dur = 0.18) => {
    MV.tl.fromTo("#flash", { backgroundColor: color, autoAlpha: peak }, { autoAlpha: 0, duration: dur, ease: "power2.out", immediateRender: false }, t0);
  };
  // Glitch: fatias finas deslocadas + separação RGB no conteúdo (registro único → sem conflito entre vários hits)
  MK.glitches = [];
  MK.glitchHit = (t0, dur = 0.16) => MK.glitches.push({ t0, dur });
  MV.onFrame((t) => {
    const g = document.getElementById("glitch"), c = document.getElementById("content"); if (!g || !c) return;
    const hit = MK.glitches.find((h) => t >= h.t0 && t < h.t0 + h.dur);
    if (!hit) { g.style.opacity = 0; c.style.filter = ""; c.style.transform = ""; return; }
    const r = MK.rng(Math.floor(t * 60) * 7 + 13); const k = 1 - (t - hit.t0) / hit.dur;
    const top = r() * 85, h = 2 + r() * 9;
    g.style.opacity = (0.35 * k + 0.1).toFixed(3);
    g.style.clipPath = `inset(${top.toFixed(1)}% 0 ${(100 - top - h).toFixed(1)}% 0)`;
    g.style.transform = `translateX(${((r() - 0.5) * 80).toFixed(1)}px)`;
    const o = (4 + 10 * k * r()).toFixed(1);
    c.style.filter = `drop-shadow(${o}px 0 0 rgba(255,0,90,.75)) drop-shadow(-${o}px 0 0 rgba(0,240,255,.75))`;
    c.style.transform = `translateX(${((r() - 0.5) * 24 * k).toFixed(1)}px)`;
  });
  // Transições entre cenas (pattern interrupt + SFX)
  MK.transition = function (name, t0, theme) {
    const sfx = (theme && theme.sfx) || {};
    // O 1º quadro vira a "capa" no feed: nunca cobri-lo com flash/glitch
    if (t0 < 0.1 && (name === "flash" || name === "glitch")) name = "punch";
    switch (name) {
      case "punch": MK.punch(t0, 0.14, 0.45); MV.cue(t0 - 0.03, sfx.transition || "whoosh", 0.8); break;
      case "flash": MK.flash(t0, theme && theme.colors && theme.colors.flash || "#fff"); MK.punch(t0, 0.08, 0.4); MV.cue(t0, sfx.impact || "impact", 0.9); break;
      case "shake": MK.shake(t0, { dur: 0.3, amp: 22 }); MK.punch(t0, 0.1, 0.35); MV.cue(t0, sfx.impact || "impact", 0.9); break;
      case "whip":
        MV.tl.fromTo("#zoom", { x: 260, filter: "blur(16px)" }, { x: 0, filter: "blur(0px)", duration: 0.32, ease: "expo.out", immediateRender: false }, t0);
        MV.cue(t0 - 0.06, sfx.transition || "whoosh", 0.9); break;
      case "glitch": MK.glitchHit(t0); MK.punch(t0, 0.06, 0.25); MV.cue(t0, sfx.glitch || "glitch", 0.8); break;
      case "zoom": MV.tl.fromTo("#zoom", { scale: 0.82, filter: "blur(12px)" }, { scale: 1, filter: "blur(0px)", duration: 0.45, ease: "expo.out", immediateRender: false }, t0); MV.cue(t0 - 0.05, sfx.transition || "whoosh", 0.8); break;
      case "none": default: break;
    }
  };

  /* ---------------- destaque (highlight) ---------------- */
  // scaleTarget deve ser um elemento que NÃO está sendo animado pela entrada (evita conflito de tweens)
  MK.highlight = function (wordEl, t0, style = "color", theme = {}, scaleTarget = null) {
    if (style === "marker" || style === "box") {
      const bar = document.createElement("span"); bar.className = "mk-marker mk-" + style; wordEl.prepend(bar);
      MV.tl.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: 0.35, ease: "expo.out", immediateRender: true }, t0);
      if (style === "box") MV.tl.set(wordEl, { attr: { "data-boxed": "1" } }, t0 + 0.05);
    }
    MV.tl.fromTo(scaleTarget || wordEl, { scale: 1 }, { scale: 1.12, duration: 0.12, ease: "power2.out", yoyo: true, repeat: 1, immediateRender: false }, t0);
  };

  /* ---------------- contador (count-up determinístico) ---------------- */
  MK.counter = function (el, t0, dur, { from = 0, to = 100, decimals = 0, prefix = "", suffix = "", locale = "pt-BR" } = {}) {
    const fmt = new Intl.NumberFormat(locale, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    MK.track(t0, dur, (p) => { const e = 1 - Math.pow(1 - p, 4); el.textContent = prefix + fmt.format(from + (to - from) * e) + suffix; });
  };
  // Scramble determinístico (letras embaralhando até revelar)
  MK.scramble = function (el, text, t0, dur = 0.8, set = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#$%&@") {
    const target = Array.from(text);
    MK.track(t0, dur, (p, t) => {
      if (p <= 0) { el.textContent = ""; return; }
      const r = MK.rng(Math.floor(t * 30) + 3); const n = Math.floor(p * target.length * 1.0001);
      el.textContent = target.map((ch, i) => (i < n || ch === " " ? ch : set[Math.floor(r() * set.length)])).join("");
    });
  };

  /* ---------------- legendas estilo karaokê (palavra a palavra) ---------------- */
  // words: [{w, s, e}] com tempos em segundos (gerados por scripts/tts.py)
  MK.chunkWords = function (words, { maxWords = 3, maxChars = 18, gap = 0.28 } = {}) {
    const chunks = []; let cur = [];
    words.forEach((wd, i) => {
      const len = cur.reduce((a, x) => a + x.w.length + 1, 0) + wd.w.length;
      const prev = words[i - 1];
      const brk = cur.length && (cur.length >= maxWords || len > maxChars || (prev && wd.s - prev.e > gap) || /[.!?…:]$/.test(prev ? prev.w : ""));
      if (brk) { chunks.push(cur); cur = []; }
      cur.push(wd);
    });
    if (cur.length) chunks.push(cur);
    return chunks;
  };
  MK.captions = function (container, words, theme = {}, opts = {}) {
    const cfg = Object.assign({ maxWords: 3, maxChars: 18, upper: true, pop: true, emph: [] }, theme.captions || {}, opts);
    const norm = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\w%$]/g, "");
    const emph = new Set((cfg.emph || []).map(norm));
    const chunks = MK.chunkWords(words, cfg);
    chunks.forEach((ch, ci) => {
      const line = document.createElement("div"); line.className = "mk-cap"; container.appendChild(line);
      ch.forEach((wd, wi) => {
        const s = document.createElement("span"); s.className = "cw" + (emph.has(norm(wd.w)) ? " emph" : "");
        s.setAttribute("data-on", "0"); s.textContent = cfg.upper ? wd.w.toLocaleUpperCase("pt-BR") : wd.w; line.appendChild(s);
        if (wi < ch.length - 1) line.appendChild(document.createTextNode(" "));
      });
      const t0 = ch[0].s, next = chunks[ci + 1];
      const t1 = next ? Math.min(next[0].s, ch[ch.length - 1].e + 0.6) : ch[ch.length - 1].e + 0.4;
      gsap.set(line, { autoAlpha: 0 });
      MV.tl.set(line, { autoAlpha: 1 }, t0);
      if (cfg.pop) MV.tl.fromTo(line, { scale: 0.82, y: 14 }, { scale: 1, y: 0, duration: 0.16, ease: "back.out(3)", immediateRender: false }, t0);
      MV.tl.set(line, { autoAlpha: 0 }, t1);
      line.querySelectorAll(".cw").forEach((span, k) => {
        const wd = ch[k];
        MV.tl.set(span, { attr: { "data-on": "1" } }, wd.s);
        if (span.classList.contains("emph")) { MV.tl.fromTo(span, { scale: 1 }, { scale: 1.18, duration: 0.1, yoyo: true, repeat: 1, ease: "power2.out", immediateRender: false }, wd.s); MV.cue(wd.s, (theme.sfx || {}).emphasis || "pop", 0.6); }
      });
    });
  };

  /* ---------------- fundos e texturas (procedurais e determinísticos) ---------------- */
  MK.background = function (bgEl, bg = {}, colors = {}) {
    const type = bg.type || "gradient";
    const c1 = bg.c1 || colors.bg || "#0b0b0f", c2 = bg.c2 || colors.bg2 || "#1c1c28";
    if (type === "solid") { bgEl.style.background = c1; }
    // gradiente e mesh são desenhados num canvas pequeno e ampliado (suave = invisível a diferença, ~10x mais rápido)
    const rgba = (hex, a) => { const h = hex.replace("#", ""); const n = parseInt(h.length === 3 ? h.split("").map((x) => x + x).join("") : h.slice(0, 6), 16); return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`; };
    if (type === "gradient" || type === "mesh") {
      const cv = document.createElement("canvas"); cv.className = "mk-bgcanvas"; cv.width = Math.round(MV.width / 5); cv.height = Math.round(MV.height / 5); bgEl.appendChild(cv);
      const ctx = cv.getContext("2d"); const Wc = cv.width, Hc = cv.height;
      const blobs = (bg.blobs || [colors.accent || "#ffd400", colors.accent2 || "#00e0ff", c2]);
      const alpha = bg.alpha != null ? (typeof bg.alpha === "string" ? parseInt(bg.alpha, 16) / 255 : bg.alpha) : 0.33;
      MV.onFrame((t) => {
        if (type === "gradient") {
          const a = (160 + MK.noise(t * 0.15, 3) * 25) * Math.PI / 180, dx = Math.sin(a) * Hc * 0.6, dy = -Math.cos(a) * Hc * 0.6;
          const g = ctx.createLinearGradient(Wc / 2 - dx, Hc / 2 - dy, Wc / 2 + dx, Hc / 2 + dy); g.addColorStop(0, c1); g.addColorStop(1, c2);
          ctx.fillStyle = g; ctx.fillRect(0, 0, Wc, Hc); return;
        }
        ctx.fillStyle = c1; ctx.fillRect(0, 0, Wc, Hc);
        blobs.forEach((c, i) => {
          const x = (0.5 + MK.noise(t * 0.12, 10 + i) * 0.38) * Wc, y = (0.45 + MK.noise(t * 0.1, 20 + i) * 0.32) * Hc;
          const r = (bg.size || 45) / 100 * Math.hypot(Wc, Hc) * 0.75;
          const g = ctx.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, rgba(c, alpha)); g.addColorStop(1, rgba(c, 0));
          ctx.fillStyle = g; ctx.fillRect(0, 0, Wc, Hc);
        });
      });
    }
    if (type === "grid") {
      bgEl.style.background = c1;
      const g = document.createElement("div"); g.className = "mk-grid"; bgEl.appendChild(g);
      g.style.setProperty("--grid-color", bg.line || "rgba(255,255,255,.07)");
      MV.onFrame((t) => { g.style.backgroundPosition = `0px ${((t * (bg.speed || 40)) % 80).toFixed(2)}px`; });
    }
    if (bg.vignette !== false) { const v = document.createElement("div"); v.className = "mk-vignette"; bgEl.appendChild(v); }
  };
  MK.grain = function (canvas, { opacity = 0.07, fps = 24, size = 270 } = {}) {
    // No render final o grão é aplicado pelo ffmpeg (muito mais rápido); aqui só para o preview no navegador
    if (!canvas || navigator.webdriver) return; canvas.width = size; canvas.height = Math.round(size * MV.height / MV.width); canvas.style.opacity = opacity;
    const ctx = canvas.getContext("2d"); const img = ctx.createImageData(canvas.width, canvas.height);
    let last = -1;
    MV.onFrame((t) => {
      const f = Math.floor(t * fps); if (f === last) return; last = f;
      const r = MK.rng(f + 99); const d = img.data;
      for (let i = 0; i < d.length; i += 4) { const v = (r() * 255) | 0; d[i] = d[i + 1] = d[i + 2] = v; d[i + 3] = 255; }
      ctx.putImageData(img, 0, 0);
    });
  };
  MK.particles = function (canvas, { count = 40, color = "rgba(255,255,255,.5)", speed = 40, size = [2, 6], seed = 5 } = {}) {
    if (!canvas) return; canvas.width = MV.width; canvas.height = MV.height; const ctx = canvas.getContext("2d");
    const r = MK.rng(seed); const ps = Array.from({ length: count }, () => ({ x: r() * MV.width, y: r() * MV.height, s: size[0] + r() * (size[1] - size[0]), v: 0.4 + r(), ph: r() * 10 }));
    MV.onFrame((t) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height); ctx.fillStyle = color;
      for (const p of ps) {
        const y = ((p.y - t * speed * p.v) % MV.height + MV.height) % MV.height; const x = p.x + Math.sin(t * 0.8 + p.ph) * 20;
        ctx.globalAlpha = 0.4 + 0.6 * Math.abs(Math.sin(t + p.ph)); ctx.beginPath(); ctx.arc(x, y, p.s, 0, Math.PI * 2); ctx.fill();
      }
    });
  };
  // Barra de progresso (aumenta retenção: o espectador vê que falta pouco)
  MK.progress = function (el) { if (!el) return; MV.onFrame((t) => { el.style.transform = `scaleX(${MK.clamp(t / Math.max(MV.duration, 0.01)).toFixed(4)})`; }); };

  /* ---------------- seek (chamado pelo renderizador a cada quadro) ---------------- */
  MV.seek = async function (t) {
    MV.tl.seek(t, false);
    for (const fn of MV.frameFns) fn(t);
    document.getAnimations().forEach((a) => { try { a.pause(); a.currentTime = t * 1000; } catch (e) {} });
    const vids = [...document.querySelectorAll("video[data-start]")];
    await Promise.all(vids.map((v) => new Promise((res) => {
      const lt = Math.max(0, t - parseFloat(v.dataset.start || 0)) * (parseFloat(v.dataset.rate || 1)) + parseFloat(v.dataset.offset || 0);
      if (Math.abs(v.currentTime - lt) < 1e-4) return res();
      v.addEventListener("seeked", res, { once: true }); v.currentTime = lt;
    })));
  };

  /* ---------------- checagem de texto/fonte (usada pelo preflight) ---------------- */
  MV.collectTexts = function () {
    const out = []; const seen = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
    for (let el = walker.currentNode; el; el = walker.nextNode()) {
      if (/^(SCRIPT|STYLE|CANVAS|svg)$/i.test(el.tagName)) continue;
      if (el.matches(".mk-text, .mk-cap, [data-qa-text], .num, .label, .kicker, h1, h2, h3, p")) {
        const txt = el.innerText !== undefined ? el.textContent.replace(/\s+/g, " ").trim() : "";
        if (!txt || seen.has(el)) continue; seen.add(el);
        const cs = getComputedStyle(el);
        out.push({ text: txt, family: cs.fontFamily, weight: cs.fontWeight, style: cs.fontStyle, cls: el.className });
      }
    }
    return out;
  };
  MV.checkFonts = async function () {
    const problems = []; const declared = new Map();
    for (const f of document.fonts) { try { await f.load(); } catch (e) { problems.push(`Fonte "${f.family}" falhou ao carregar: ${e.message}`); } declared.set(f.family.replace(/["']/g, ""), f.status); }
    const cnv = document.createElement("canvas").getContext("2d");
    const entries = MV.collectTexts(); const glyphMissing = {};
    for (const e of entries) {
      const fam = e.family.split(",")[0].trim().replace(/["']/g, "");
      if (!declared.has(fam)) { problems.push(`Fonte "${fam}" não está declarada/carregada (o navegador usaria fallback) — texto: "${e.text.slice(0, 40)}"`); continue; }
      for (const ch of new Set(Array.from(e.text))) {
        if (/\s/.test(ch)) continue;
        cnv.font = `${e.style} ${e.weight} 100px "${fam}", monospace`; const a = cnv.measureText(ch).width;
        cnv.font = `${e.style} ${e.weight} 100px "${fam}", serif`; const b = cnv.measureText(ch).width;
        if (Math.abs(a - b) > 0.01) (glyphMissing[fam] = glyphMissing[fam] || new Set()).add(ch);
      }
    }
    Object.entries(glyphMissing).forEach(([fam, set]) => problems.push(`Fonte "${fam}" NÃO tem os glifos: ${[...set].join(" ")} (aparecerão com outra fonte — troque a fonte ou o caractere)`));
    return { problems, texts: entries };
  };
  // Verifica layout num instante t: texto visível fora da tela, fora da safe zone, cortado ou sobreposto
  MV.checkLayout = function (t, safe) {
    const issues = []; const els = [...document.querySelectorAll(".mk-text, .mk-cap, [data-qa-text]")];
    const vis = (el) => { for (let n = el; n && n !== document.body; n = n.parentElement) { const cs = getComputedStyle(n); if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.05) return false; } return true; };
    const boxes = [];
    for (const el of els) {
      if (!vis(el) || !el.textContent.trim()) continue;
      const r = el.getBoundingClientRect(); if (r.width < 2) continue;
      const label = `"${el.textContent.trim().slice(0, 30)}" @${t.toFixed(2)}s`;
      if (r.left < -2 || r.top < -2 || r.right > MV.width + 2 || r.bottom > MV.height + 2) issues.push({ level: "erro", t, msg: `Texto saindo da tela ${label}` });
      else if (safe && !el.closest("[data-qa-ignore-safe]") && (r.left < safe.left || r.right > MV.width - safe.right || r.top < safe.top || r.bottom > MV.height - safe.bottom)) issues.push({ level: "aviso", t, msg: `Texto fora da safe zone (UI do TikTok pode cobrir) ${label}` });
      if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== "visible") issues.push({ level: "erro", t, msg: `Texto cortado (overflow) ${label}` });
      boxes.push({ r, label, el });
    }
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i], b = boxes[j]; if (a.el.contains(b.el) || b.el.contains(a.el)) continue;
      const ix = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left), iy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
      if (ix > 12 && iy > 12) issues.push({ level: "aviso", t, msg: `Textos sobrepostos ${a.label} x ${b.label}` });
    }
    return issues;
  };
})();
