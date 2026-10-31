/* =====================================================================
   SCENES — monta o vídeo inteiro a partir de data.json + tema (estilo)
   Tipos de cena: hook | text | quote | list | stat | cta | image | html
   ===================================================================== */
(function () {
  "use strict";
  const MV = window.MV, MK = window.MK;

  const loadCSS = (href) => new Promise((res) => { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = href; l.onload = res; l.onerror = () => { MV.warn("CSS não encontrado: " + href); res(); }; document.head.appendChild(l); });
  const loadJS = (src) => new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = () => rej(new Error("JS não encontrado: " + src)); document.head.appendChild(s); });
  const deepMerge = (a, b) => { const o = Array.isArray(a) ? a.slice() : Object.assign({}, a); for (const k in b || {}) o[k] = b[k] && typeof b[k] === "object" && !Array.isArray(b[k]) ? deepMerge(a && a[k] || {}, b[k]) : b[k]; return o; };
  const norm = (s) => String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9%$]/g, "");

  // Associa cada palavra exibida ao instante em que ela é FALADA (sincronia voz ↔ texto)
  function alignTimes(shownWords, spoken, t0, t1) {
    const times = new Array(shownWords.length).fill(null); let p = 0;
    shownWords.forEach((w, i) => {
      const n = norm(w); if (!n) return;
      for (let k = p; k < Math.min(spoken.length, p + 5); k++) {
        const sn = norm(spoken[k].w);
        if (sn === n || (n.length > 3 && (sn.startsWith(n) || n.startsWith(sn)) && sn.length > 2)) { times[i] = spoken[k].s; p = k + 1; break; }
      }
    });
    // interpola as que não casaram (ex.: "90%" exibido vs "noventa por cento" falado)
    for (let i = 0; i < times.length; i++) if (times[i] == null) {
      let a = i - 1; while (a >= 0 && times[a] == null) a--; let b = i + 1; while (b < times.length && times[b] == null) b++;
      const ta = a >= 0 ? times[a] : t0, tb = b < times.length ? times[b] : Math.min(t1 - 0.3, (spoken.length ? spoken[spoken.length - 1].s : t0 + 0.3));
      const span = Math.max(0, tb - ta), nGap = b - a;
      times[i] = ta + span * (i - a) / nGap;
    }
    return times.map((x) => Math.max(t0, x));
  }

  // Imagem/vídeo da cena: layout "cover" (fundo em tela cheia), "card" (cartão no topo) ou "float" (PNG recortado flutuando)
  function addMedia(el, src, sc, theme) {
    const layout = sc.imageLayout || (theme.imageLayout) || "cover";
    const isVid = /\.(mp4|webm|mov)$/i.test(src);
    const wrap = document.createElement("div"); wrap.className = `mk-media mk-media-${layout}`; el.appendChild(wrap);
    el.classList.add(`has-${layout}`);
    const m = document.createElement(isVid ? "video" : "img"); m.src = src; m.className = "media";
    if (isVid) { m.muted = true; m.preload = "auto"; m.playsInline = true; m.dataset.start = sc.start; m.dataset.offset = sc.offset || 0; }
    if (sc.imagePos) m.style.objectPosition = sc.imagePos;
    wrap.appendChild(m);
    const d = Math.max(0.5, sc.end - sc.start);
    if (layout === "cover") {
      const sh = document.createElement("div"); sh.className = "mk-shade"; wrap.appendChild(sh);
      const kb = sc.kenburns || "in"; // in | out | left | right | none
      const from = { in: { scale: 1.02 }, out: { scale: 1.16 }, left: { scale: 1.12, xPercent: 3 }, right: { scale: 1.12, xPercent: -3 }, none: { scale: 1 } }[kb];
      const to = { in: { scale: 1.16 }, out: { scale: 1.02 }, left: { scale: 1.12, xPercent: -3 }, right: { scale: 1.12, xPercent: 3 }, none: { scale: 1 } }[kb];
      MV.tl.fromTo(m, from, Object.assign({ duration: d, ease: "none", immediateRender: false }, to), sc.start);
    } else if (layout === "card") {
      MV.tl.from(wrap, { scale: 0.86, y: 60, autoAlpha: 0, rotation: -2, duration: 0.55, ease: "back.out(1.6)", immediateRender: false }, sc.start);
      MV.tl.fromTo(m, { scale: 1.12 }, { scale: 1.0, duration: d, ease: "none", immediateRender: false }, sc.start);
      MV.cue(sc.start, (theme.sfx || {}).transition || "swoosh", 0.5);
    } else if (layout === "float") {
      MV.tl.from(wrap, { scale: 0.6, autoAlpha: 0, y: 120, duration: 0.6, ease: "back.out(1.8)", immediateRender: false }, sc.start);
      MV.onFrame((t) => { if (t >= sc.start && t <= sc.end) m.style.transform = `translateY(${(Math.sin((t - sc.start) * 2.2) * 14).toFixed(2)}px) rotate(${(Math.sin((t - sc.start) * 1.3) * 1.5).toFixed(2)}deg)`; });
    }
    return wrap;
  }

  function textScene(el, sc, theme, type) {
    const box = document.createElement("div"); box.className = "textbox"; el.appendChild(box);
    if (sc.kicker) { const k = document.createElement("div"); k.className = "kicker"; k.textContent = sc.kicker; box.appendChild(k); MV.tl.add(MK.enter.fade(k, { dur: 0.35 }), sc.start + 0.02); }
    if (type === "list" && sc.num != null) { const n = document.createElement("div"); n.className = "list-num"; n.textContent = sc.num; box.appendChild(n); MV.tl.add(MK.enter.pop(n), sc.start); }
    const tx = document.createElement("div"); tx.className = "mk-text " + type; box.appendChild(tx);
    const preset = sc.enter || (theme.enter || {})[type] || (theme.enter || {}).default || "pop";
    const upper = sc.upper != null ? sc.upper : theme.upper;
    const parts = MK.splitText(tx, sc.show || "", { upper, chars: preset === "type" || theme.chars });
    if (preset === "rise") tx.classList.add("masked");
    const fit = Object.assign({}, theme.fit || {}, (theme.fitByType || {})[type] || {}, sc.fit || {});
    // reserva espaço para o micro-zoom contínuo (idle) e para o "pop" do destaque não vazarem da safe zone
    const idle = sc.idle != null ? sc.idle : theme.idle != null ? theme.idle : 0.04;
    fit.width = fit.width || Math.floor(box.clientWidth / (1 + idle + 0.04));
    // altura disponível = caixa segura − número/kicker − espaçamentos (evita estourar a safe zone com 4+ linhas)
    const others = [...box.children].filter((c) => c !== tx).reduce((a, c) => a + c.offsetHeight + 28, 0);
    fit.height = fit.height || Math.floor((box.clientHeight - others) * 0.92 / (1 + idle));
    MK.fit(tx, fit);
    return { tx, parts, preset };
  }

  function animateText(sc, theme, { tx, parts, preset }, i) {
    const t0 = sc.start + 0.02;
    const targetsFor = (w) => preset === "rise" || preset === "scramble" ? w.firstChild : preset === "type" ? w.querySelectorAll(".c") : w;
    const shown = parts.words.map((w) => w.dataset.word);
    // gancho: frase inteira em ~0,5 s (quem rola sem som lê na hora); demais cenas: palavra no instante em que é falada
    const sync = (sc.sync != null ? sc.sync : (sc.type !== "hook" || theme.syncHook) && theme.sync !== false) && sc.words && sc.words.length;
    const times = sync ? alignTimes(shown, sc.words, t0, sc.end) : shown.map((_, k) => t0 + k * ((theme.stagger != null ? theme.stagger : 0.07)));
    parts.words.forEach((w, k) => {
      const e = MK.enter[preset] ? MK.enter[preset](targetsFor(w), { stagger: preset === "type" ? 0.03 : 0 }) : MK.enter.pop(w);
      if (i === 0 && times[k] <= sc.start + 0.06 && preset !== "type" && preset !== "scramble") {
        // gancho: no quadro 0 a primeira palavra já está legível (entrada ~55% concluída), mas ainda em movimento
        e.pause(); MV.tl.add(e.tweenFromTo(Math.min(0.2, e.duration() * 0.55), e.duration(), { ease: "none" }), 0);
      } else MV.tl.add(e, times[k]);
      if (w.classList.contains("hl") || w.classList.contains("hl2")) {
        MK.highlight(w, times[k] + 0.12, sc.highlight || theme.highlight || "color", theme, preset === "rise" || preset === "scramble" ? w : w.firstChild);
        MV.cue(times[k] + 0.04, (theme.sfx || {}).emphasis || "pop", 0.7);
        if (theme.shakeOnEmphasis) MK.shake(times[k] + 0.04, { dur: 0.25, amp: 10 });
      } else if (sync && (theme.sfx || {}).word) MV.cue(times[k], theme.sfx.word, 0.35);
    });
    if (preset === "type") { const n = parts.words.reduce((a, w) => a + w.querySelectorAll(".c").length, 0); for (let c = 0; c < n; c += 2) MV.cue(t0 + c * 0.03, (theme.sfx || {}).type || "click", 0.25); }
    // micro-movimento contínuo: a tela nunca fica "parada" (segura a atenção)
    const idle = sc.idle != null ? sc.idle : theme.idle != null ? theme.idle : 0.04;
    if (idle) MV.tl.fromTo(tx, { scale: 1 }, { scale: 1 + idle, duration: Math.max(0.3, sc.end - sc.start), ease: "none", immediateRender: false }, sc.start);
    // saída
    const ex = sc.exit || theme.exit || "up"; const d = MK.exitDur[ex] || 0.2;
    if (!sc.last || sc.exitLast) MV.tl.add(MK.exit[ex](tx.parentElement), Math.max(sc.start + 0.3, sc.end - d));
  }

  const builders = {
    hook: (el, sc, th, i) => animateText(sc, th, textScene(el, sc, th, "hook"), i),
    text: (el, sc, th, i) => animateText(sc, th, textScene(el, sc, th, "text"), i),
    quote: (el, sc, th, i) => animateText(sc, th, textScene(el, sc, th, "quote"), i),
    list: (el, sc, th, i) => animateText(sc, th, textScene(el, sc, th, "list"), i),
    cta: (el, sc, th, i) => animateText(sc, th, textScene(el, sc, th, "cta"), i),
    stat: (el, sc, th) => {
      const box = document.createElement("div"); box.className = "textbox stat"; el.appendChild(box);
      const num = document.createElement("div"); num.className = "num"; num.setAttribute("data-qa-text", ""); box.appendChild(num);
      const v = sc.value || { to: 100 }; const fmt = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: v.decimals || 0, maximumFractionDigits: v.decimals || 0 });
      num.textContent = (v.prefix || "") + fmt.format(v.to) + (v.suffix || ""); // valor final (para medir e checar)
      const dur = v.dur || Math.min(1.4, (sc.end - sc.start) * 0.6);
      MV.tl.add(MK.enter.pop(num), sc.start + 0.02);
      MK.counter(num, sc.start + 0.02, dur, v);
      MV.cue(sc.start, (th.sfx || {}).stat || "riser", 0.6); MV.cue(sc.start + dur, (th.sfx || {}).impact || "impact", 0.8);
      MK.punch(sc.start + dur, 0.06, 0.35);
      if (sc.show) {
        const lb = document.createElement("div"); lb.className = "mk-text label"; box.appendChild(lb);
        const parts = MK.splitText(lb, sc.show, { upper: sc.upper != null ? sc.upper : th.upper }); MK.fit(lb, Object.assign({ max: 90, min: 40, maxLines: 3, width: Math.floor(box.clientWidth * 0.9) }, sc.fit || {}));
        MV.tl.add(MK.enter.fade(parts.words, { stagger: 0.05 }), sc.start + Math.min(dur * 0.5, 0.5));
      }
      const idle = sc.idle != null ? sc.idle : th.idle != null ? th.idle : 0.04;
      if (idle) MV.tl.fromTo(box, { scale: 1 }, { scale: 1 + idle, duration: Math.max(0.3, sc.end - sc.start), ease: "none", immediateRender: false }, sc.start);
      const ex = sc.exit || th.exit || "up"; if (!sc.last) MV.tl.add(MK.exit[ex](box), Math.max(sc.start + 0.3, sc.end - (MK.exitDur[ex] || 0.2)));
    },
    image: (el, sc, th, i) => {
      addMedia(el, sc.src || sc.image, sc, th);
      if (sc.show) animateText(sc, th, textScene(el, sc, th, "text"), i);
    },
    html: (el, sc, th) => { el.innerHTML = sc.html || ""; el.querySelectorAll("[data-anim]").forEach((n, k) => MV.tl.add((MK.enter[n.dataset.anim] || MK.enter.pop)(n), sc.start + 0.02 + k * 0.08)); },
  };

  MV.sceneBuilders = builders; // custom.js pode registrar tipos novos: MV.sceneBuilders.meuTipo = (el, sc, theme, i) => {...}
  MV.textScene = textScene; MV.animateText = animateText;

  MV.boot = async function (dataUrl = "data.json") {
    try {
      const data = await (await fetch(dataUrl)).json(); MV.data = data;
      const meta = data.meta || {}; MV.fps = meta.fps || 60; MV.width = meta.width || 1080; MV.height = meta.height || 1920;
      const style = data.style || "kinetic-impact";
      const base = data.styleDir || `/_mv/styles/${style}`;
      await loadCSS(`${base}/theme.css`); await loadJS(`${base}/theme.js`);
      if ((MV.themes[style] || {}).custom) await loadJS(`${base}/custom.js`); // presets/cenas exclusivos do estilo
      for (const c of (meta.css || [])) await loadCSS(c);
      for (const j of (meta.js || [])) await loadJS(j);
      const theme = deepMerge(MV.themes[style] || {}, data.theme || {}); MV.theme = theme;
      // variáveis CSS do tema
      const root = document.documentElement.style;
      Object.entries(theme.colors || {}).forEach(([k, v]) => root.setProperty(`--${k}`, v));
      Object.entries(theme.fonts || {}).forEach(([k, v]) => root.setProperty(`--font-${k}`, `"${v}"`));
      root.setProperty("--W", MV.width + "px"); root.setProperty("--H", MV.height + "px");
      document.body.classList.add("style-" + style);

      // garante que TODAS as fontes estão carregadas antes de medir/animar
      await Promise.all([...document.fonts].map((f) => f.load().catch(() => null))); await document.fonts.ready;

      MK.background(document.getElementById("bg"), theme.bg || {}, theme.colors || {});
      if (theme.grain) MK.grain(document.getElementById("grain"), { opacity: theme.grain });
      if (theme.particles) MK.particles(document.getElementById("particles"), theme.particles);
      if (theme.progress) MK.progress(document.getElementById("progress")); else document.getElementById("progress").style.display = "none";

      const scenes = data.scenes || []; const content = document.getElementById("content");
      scenes.forEach((sc, i) => {
        sc.last = i === scenes.length - 1;
        const el = document.createElement("div"); el.className = `scene scene-${sc.type || "text"}`; el.id = sc.id || `s${i}`; content.appendChild(el);
        if (sc.className) el.classList.add(...sc.className.split(/\s+/));
        gsap.set(el, { autoAlpha: 0 }); MV.tl.set(el, { autoAlpha: 1 }, sc.start); if (!sc.last) MV.tl.set(el, { autoAlpha: 0 }, sc.end);
        const tr = sc.transition || (i === 0 ? theme.hookTransition : (theme.transitions ? theme.transitions[(i - 1) % theme.transitions.length] : theme.transition));
        if (tr) MK.transition(tr, sc.start, theme);
        if ((theme.sfx || {}).enter && i > 0 && !tr) MV.cue(sc.start, theme.sfx.enter, 0.5);
        if (sc.image && sc.type !== "image") addMedia(el, sc.image, sc, theme);
        (builders[sc.type] || builders.text)(el, sc, theme, i);
      });

      if (data.captions && data.captions.enabled && data.words && data.words.length) MK.captions(document.getElementById("captions"), data.words, theme, data.captions);
      else document.getElementById("captions").style.display = "none";

      const end = scenes.length ? scenes[scenes.length - 1].end : 0;
      MV.duration = meta.duration || Math.max(end, data.audioDuration || 0) || MV.tl.duration();
      MV.tl.set({}, {}, MV.duration); // estende a timeline até o fim
      if (typeof window.MV_CUSTOM === "function") await window.MV_CUSTOM(data, theme);
      // espera todas as imagens decodificarem e os vídeos carregarem (sem quadro em branco no render)
      await Promise.all([...document.images].map((im) => im.decode().catch(() => MV.warn("Imagem não carregou: " + im.getAttribute("src")))));
      await Promise.all([...document.querySelectorAll("video")].map((v) => v.readyState >= 2 ? 0 : new Promise((r) => { v.addEventListener("loadeddata", r, { once: true }); v.addEventListener("error", () => { MV.warn("Vídeo não carregou: " + v.getAttribute("src")); r(); }, { once: true }); })));
      MV.cues.sort((a, b) => a.t - b.t);
      await MV.seek(0);
      window.__MV_READY = true;
      if (!navigator.webdriver) MV.preview(data);
    } catch (e) { console.error(e); window.__MV_ERROR = String(e && e.stack || e); }
  };

  // Pré-visualização ao abrir no navegador (fora do renderizador): espaço = play/pause, ?t=2.5 congela, ?safe mostra safe zone
  MV.preview = function (data) {
    const q = new URLSearchParams(location.search); if (q.has("safe")) document.body.classList.add("show-safe");
    const fit = () => { const s = Math.min(innerWidth / MV.width, innerHeight / MV.height); document.getElementById("stage").style.transform = `scale(${s})`; };
    fit(); addEventListener("resize", fit);
    if (q.has("t")) { MV.seek(parseFloat(q.get("t"))); return; }
    const audio = data.audio ? new Audio(data.audio) : null; let t0 = null, playing = true, tp = 0;
    const loop = (now) => { if (playing) { if (t0 == null) t0 = now - tp * 1000; tp = ((now - t0) / 1000) % MV.duration; MV.seek(tp); } requestAnimationFrame(loop); };
    addEventListener("keydown", (e) => { if (e.code === "Space") { playing = !playing; t0 = null; if (audio) playing ? (audio.currentTime = tp, audio.play()) : audio.pause(); } });
    if (audio) audio.play().catch(() => {});
    requestAnimationFrame(loop);
  };
})();
