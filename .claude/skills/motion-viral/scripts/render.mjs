#!/usr/bin/env node
/* =====================================================================
   RENDER — renderizador determinístico quadro-a-quadro (Chromium + ffmpeg)
   Cada quadro é calculado no tempo exato t = frame/fps, capturado em PNG
   sem perdas e codificado em H.264 CFR. Resultado: movimento 100% fluido,
   sem frame perdido/duplicado, independentemente da velocidade da máquina.

   Uso:
     node render.mjs <pasta-do-projeto> [opções]
   Opções:
     --out <arq.mp4>       saída (padrão: <projeto>/out/<nome>.mp4)
     --fps <n>             sobrescreve fps (padrão: data.meta.fps ou 60)
     --workers <n>         páginas em paralelo (padrão: nº de CPUs, máx 6)
     --crf <n>             qualidade x264 (padrão 16; menor = melhor)
     --maxrate <n>M        teto de bitrate (padrão 35M ≈ 4–5 MB/s; o arquivo fica leve p/ upload)
     --mblur <n>           motion blur com n subquadros (ex.: 4). Mais cinematográfico, n× mais lento
     --shutter <0..1>      fração do obturador p/ motion blur (padrão 0.5 = 180°)
     --draft               rascunho rápido: 30 fps, meia resolução, sem motion blur
     --stills <t1,t2,...>  só exporta PNGs nesses tempos (s) para revisão visual
     --review              exporta stills automáticos (início/meio/fim de cada cena) + contact sheet
     --safe                desenha a safe zone nos stills
     --preflight-only      só roda as checagens (fontes, glifos, layout) e sai
     --force               renderiza mesmo com erros de preflight (NÃO recomendado)
     --no-audio            não mixa o áudio
     --serve               só sobe o servidor para preview ao vivo no navegador
   ===================================================================== */
import { createRequire } from "node:module";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const require_ = createRequire(import.meta.url);
let chromium; try { ({ chromium } = require_("playwright")); } catch (e) { console.error("Playwright não encontrado. Instale: npm i -g playwright && npx playwright install chromium"); process.exit(1); }
const SKILL_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
if (!args[0] || args[0].startsWith("--")) { console.error("uso: node render.mjs <pasta-do-projeto> [opções]"); process.exit(1); }
const PROJECT = path.resolve(args[0]);
const opt = (k, d) => { const i = args.indexOf("--" + k); return i < 0 ? d : (args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : true); };
const has = (k) => args.includes("--" + k);
const BUILD = path.join(PROJECT, "build"); const QA = path.join(BUILD, "qa");
fs.mkdirSync(QA, { recursive: true });
const log = (...a) => console.log("[render]", ...a);

/* ---------- servidor estático (projeto em /, skill em /_mv/) ---------- */
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2", ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4" };
function startServer() {
  const srv = http.createServer((req, res) => {
    let u = decodeURIComponent(new URL(req.url, "http://x").pathname);
    let file = u.startsWith("/_mv/") ? path.join(SKILL_ROOT, u.slice(5)) : path.join(PROJECT, u === "/" ? "index.html" : u);
    file = path.normalize(file);
    if (!file.startsWith(SKILL_ROOT) && !file.startsWith(PROJECT)) { res.writeHead(403).end(); return; }
    fs.stat(file, (err, stt) => {
      if (err || !stt.isFile()) { res.writeHead(404).end("404 " + u); return; }
      const type = MIME[path.extname(file).toLowerCase()] || "application/octet-stream";
      const range = req.headers.range;
      if (range) {
        const [a, b] = range.replace("bytes=", "").split("-"); const start = +a, end = b ? +b : stt.size - 1;
        res.writeHead(206, { "Content-Type": type, "Content-Range": `bytes ${start}-${end}/${stt.size}`, "Accept-Ranges": "bytes", "Content-Length": end - start + 1 });
        fs.createReadStream(file, { start, end }).pipe(res);
      } else { res.writeHead(200, { "Content-Type": type, "Content-Length": stt.size, "Accept-Ranges": "bytes", "Cache-Control": "no-cache" }); fs.createReadStream(file).pipe(res); }
    });
  });
  return new Promise((r) => srv.listen(0, "127.0.0.1", () => r(srv)));
}

const data = JSON.parse(fs.readFileSync(path.join(PROJECT, "data.json"), "utf8"));
const DRAFT = has("draft");
const W = data.meta?.width || 1080, H = data.meta?.height || 1920;
const FPS = +(opt("fps", 0) || (DRAFT ? 30 : data.meta?.fps || 60));
const MBLUR = DRAFT ? 1 : Math.max(1, +opt("mblur", data.meta?.mblur || 1));
const SHUTTER = +opt("shutter", 0.5);
const CRF = +opt("crf", DRAFT ? 23 : 16);
const MAXRATE = String(opt("maxrate", DRAFT ? "8M" : "35M")); // teto de bitrate: arquivo leve p/ upload sem perda visível (TikTok re-encoda ~ 3–8 Mbps)
const DSF = DRAFT ? 0.5 : 1;
const WORKERS = Math.max(1, Math.min(+opt("workers", Math.min(6, os.cpus().length)), 12));
const SAFE = { top: 250, bottom: 560, left: 90, right: 140 };

async function openPage(browser, url, collectErrors) {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: DSF });
  const page = await ctx.newPage();
  if (collectErrors) {
    page.on("console", (m) => { if (m.type() === "error") collectErrors.push("console: " + m.text()); });
    page.on("pageerror", (e) => collectErrors.push("pageerror: " + e.message));
    page.on("requestfailed", (r) => collectErrors.push("requestfailed: " + r.url()));
    page.on("response", (r) => { if (r.status() >= 400) collectErrors.push(`HTTP ${r.status()}: ${r.url()}`); });
  }
  await page.goto(url, { waitUntil: "load" });
  await page.waitForFunction(() => window.__MV_READY || window.__MV_ERROR, null, { timeout: 120000 });
  const err = await page.evaluate(() => window.__MV_ERROR);
  if (err) throw new Error("Erro ao montar a composição:\n" + err);
  const cdp = await ctx.newCDPSession(page);
  return { page, ctx, cdp };
}
async function grab({ page, cdp }, t) {
  await page.evaluate((tt) => window.MV.seek(tt), t); // captureScreenshot já força um quadro novo (testado: determinístico)
  const { data: b64 } = await cdp.send("Page.captureScreenshot", { format: "png", optimizeForSpeed: true, fromSurface: true, captureBeyondViewport: false });
  return Buffer.from(b64, "base64");
}
function ffmpeg(argv, label) {
  const p = spawn("ffmpeg", ["-hide_banner", "-loglevel", "error", ...argv], { stdio: ["pipe", "inherit", "inherit"] });
  p.done = new Promise((res, rej) => p.on("close", (c) => (c === 0 ? res() : rej(new Error(`ffmpeg falhou (${label}) código ${c}`)))));
  return p;
}
const write = (stream, buf) => new Promise((r) => (stream.write(buf) ? r() : stream.once("drain", r)));

(async () => {
  if (has("serve")) { // preview ao vivo no navegador (com áudio): espaço = play/pause, ?t=2.5 congela, ?safe = safe zone
    const srv = await startServer(); console.log(`Preview: http://127.0.0.1:${srv.address().port}/index.html   (?safe para ver a safe zone, ?t=1.5 para congelar)`); return;
  }
  const srv = await startServer(); const url = `http://127.0.0.1:${srv.address().port}/index.html`;
  const browser = await chromium.launch({ args: ["--force-color-profile=srgb", "--font-render-hinting=none", "--disable-lcd-text", "--hide-scrollbars", "--autoplay-policy=no-user-gesture-required", "--disable-background-timer-throttling", "--disable-renderer-backgrounding"] });
  const errors = [];
  try {
    /* ================= PREFLIGHT ================= */
    const main = await openPage(browser, url, errors);
    const info = await main.page.evaluate(() => ({ grain: (window.MV.theme || {}).grain || 0, duration: window.MV.duration, cues: window.MV.cues, warnings: window.MV.warnings, scenes: (window.MV.data.scenes || []).map((s) => ({ type: s.type, start: s.start, end: s.end, show: s.show })) }));
    const fontRep = await main.page.evaluate(() => window.MV.checkFonts());
    const mediaRep = await main.page.evaluate(() => window.MV.checkMedia());
    info.warnings.push(...mediaRep.filter((m) => m.level === "aviso").map((m) => m.msg));
    const layout = []; const step = 0.1;
    for (let t = 0; t <= info.duration + 1e-6; t += step) { await main.page.evaluate((tt) => window.MV.seek(tt), t); layout.push(...(await main.page.evaluate(([tt, s]) => window.MV.checkLayout(tt, s), [t, SAFE]))); }
    // agrupa ocorrências e ignora estados transitórios (entradas/saídas/whips duram < 0.3s):
    // só conta o problema se ele PERSISTE por >= 0.3s seguidos (texto "parado" no lugar errado)
    const grouped = {}; for (const it of layout) { const k = it.level + "|" + it.msg.replace(/ @[\d.]+s/, ""); (grouped[k] = grouped[k] || { level: it.level, msg: it.msg.replace(/ @[\d.]+s/, ""), times: [] }).times.push(+it.t.toFixed(2)); }
    const maxRun = (ts) => { let best = 1, cur = 1; for (let i = 1; i < ts.length; i++) { cur = ts[i] - ts[i - 1] <= step * 1.5 ? cur + 1 : 1; best = Math.max(best, cur); } return best; };
    const layoutIssues = Object.values(grouped).filter((g) => maxRun(g.times) >= 3);
    fs.writeFileSync(path.join(QA, "texts.json"), JSON.stringify(fontRep.texts, null, 2));
    fs.writeFileSync(path.join(BUILD, "cues.json"), JSON.stringify(info.cues, null, 2));
    fs.writeFileSync(path.join(BUILD, "meta.json"), JSON.stringify({ duration: info.duration, fps: FPS, width: W, height: H, scenes: info.scenes }, null, 2));
    const pre = { fontProblems: fontRep.problems, layoutIssues, warnings: info.warnings, pageErrors: errors.slice() };
    fs.writeFileSync(path.join(QA, "preflight.json"), JSON.stringify(pre, null, 2));
    const fatal = [...pre.fontProblems, ...pre.pageErrors, ...mediaRep.filter((m) => m.level === "erro").map((m) => m.msg), ...layoutIssues.filter((x) => x.level === "erro").map((x) => `${x.msg} (t=${x.times.slice(0, 6).join(", ")}${x.times.length > 6 ? "…" : ""})`)];
    log(`duração ${info.duration.toFixed(2)}s • ${info.scenes.length} cenas • ${info.cues.length} cues de SFX • ${fontRep.texts.length} blocos de texto`);
    pre.warnings.forEach((w) => log("AVISO:", w));
    layoutIssues.filter((x) => x.level === "aviso").forEach((x) => log("AVISO:", x.msg, "t=" + x.times.slice(0, 4).join(",")));
    if (fatal.length) { log("PREFLIGHT REPROVADO:"); fatal.forEach((f) => log("  ✗", f)); if (!has("force")) { log("Corrija e rode de novo (ou --force)."); process.exitCode = 2; return; } }
    else log("preflight OK ✓ (fontes carregadas, glifos completos, nada saindo da tela)");
    if (has("preflight-only")) return;

    /* ================= STILLS PARA REVISÃO ================= */
    const stillTimes = [];
    if (opt("stills", null)) stillTimes.push(...String(opt("stills")).split(",").map(Number));
    if (has("review")) info.scenes.forEach((s) => { const d = s.end - s.start; stillTimes.push(s.start + Math.min(0.12, d * 0.1), s.start + d * 0.55, Math.max(s.start, s.end - 0.05)); });
    if (stillTimes.length) {
      const dir = path.join(BUILD, "stills"); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
      if (has("safe")) await main.page.evaluate(() => document.body.classList.add("show-safe"));
      const files = [];
      for (const t of stillTimes) { const f = path.join(dir, `t_${t.toFixed(2).padStart(6, "0")}.png`); fs.writeFileSync(f, await grab(main, Math.min(t, info.duration - 1 / FPS))); files.push(f); }
      log(`${files.length} stills em ${dir}`);
      if (has("review") && files.length) {
        const cols = 6, rows = Math.ceil(files.length / cols);
        spawnSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-pattern_type", "glob", "-i", path.join(dir, "t_*.png"), "-vf", `scale=270:-1,tile=${cols}x${rows}:padding=6:color=white`, "-frames:v", "1", path.join(BUILD, "review_sheet.png")]);
        log("contact sheet:", path.join(BUILD, "review_sheet.png"));
      }
      if (!has("render")) return;
    }
    await main.ctx.close();

    /* ================= RENDER ================= */
    const total = Math.round(info.duration * FPS);
    const per = Math.ceil(total / WORKERS);
    const segs = []; const t0 = Date.now(); let doneFrames = 0;
    const vf = [];
    if (MBLUR > 1) vf.push(`tmix=frames=${MBLUR}`, `select='eq(mod(n\\,${MBLUR})\\,${MBLUR - 1})'`, `setpts=N/(${FPS}*TB)`);
    vf.push("scale=out_color_matrix=bt709:out_range=tv", "format=yuv420p");
    if (info.grain) vf.push(`noise=c0s=${Math.round(info.grain * 70)}:c0f=t`); // grão de filme (só luma), esconde banding de gradiente
    log(`renderizando ${total} quadros @ ${FPS}fps ${W * DSF}x${H * DSF} • ${WORKERS} workers${MBLUR > 1 ? ` • motion blur ${MBLUR}x` : ""}`);
    let lastPct = -1; const progress = setInterval(() => { if (!process.stdout.isTTY) { const pct = Math.floor(doneFrames / total * 10); if (pct === lastPct) return; lastPct = pct; } const el = (Date.now() - t0) / 1000; const fps = doneFrames / el; process.stdout.write(`${process.stdout.isTTY ? "\r" : "\n"}[render] ${doneFrames}/${total} quadros • ${fps.toFixed(1)} q/s • faltam ~${((total - doneFrames) / Math.max(fps, 0.1)).toFixed(0)}s   `); }, 1000);
    await Promise.all(Array.from({ length: WORKERS }, async (_, w) => {
      const a = w * per, b = Math.min(total, a + per); if (a >= b) return;
      const seg = path.join(BUILD, `seg_${String(w).padStart(2, "0")}.mp4`); segs[w] = seg;
      const ff = ffmpeg(["-y", "-f", "image2pipe", "-c:v", "png", "-framerate", String(FPS * MBLUR), "-i", "-", "-vf", vf.join(","),
        "-c:v", "libx264", "-preset", DRAFT ? "veryfast" : String(opt("preset", "medium")), "-crf", String(CRF), "-maxrate", MAXRATE, "-bufsize", String(parseInt(MAXRATE) * 2) + "M", "-tune", "animation", "-profile:v", "high", "-level:v", "4.2",
        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
        "-r", String(FPS), "-g", String(FPS * 2), "-bf", "2", "-movflags", "+faststart", seg], "seg" + w);
      const pg = await openPage(browser, url, null);
      for (let f = a; f < b; f++) {
        for (let k = 0; k < MBLUR; k++) {
          const t = MBLUR > 1 ? Math.max(0, (f - SHUTTER * (MBLUR - 1 - k) / MBLUR) / FPS) : f / FPS;
          await write(ff.stdin, await grab(pg, t));
        }
        doneFrames++;
      }
      ff.stdin.end(); await ff.done; await pg.ctx.close();
    }));
    clearInterval(progress); process.stdout.write("\n");
    const list = path.join(BUILD, "segs.txt"); fs.writeFileSync(list, segs.filter(Boolean).map((s) => `file '${s}'`).join("\n"));
    const video = path.join(BUILD, "video.mp4");
    await ffmpeg(["-y", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", "-movflags", "+faststart", video], "concat").done;
    segs.filter(Boolean).forEach((s) => fs.rmSync(s, { force: true }));

    /* ================= ÁUDIO ================= */
    const name = (data.meta?.slug || path.basename(PROJECT)) + (DRAFT ? "_draft" : "");
    const out = path.resolve(opt("out", path.join(PROJECT, "out", name + ".mp4")));
    fs.mkdirSync(path.dirname(out), { recursive: true });
    const audio = [data.audio && path.join(PROJECT, data.audio), path.join(PROJECT, "audio", "final.wav")].find((p) => p && fs.existsSync(p));
    if (audio && !has("no-audio")) {
      await ffmpeg(["-y", "-i", video, "-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-af", "apad", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", info.duration.toFixed(3), "-movflags", "+faststart", out], "mux").done;
    } else { fs.copyFileSync(video, out); if (!has("no-audio")) log("AVISO: sem áudio (rode scripts/master_audio.py antes)"); }
    log(`pronto em ${((Date.now() - t0) / 1000).toFixed(1)}s → ${out}`);
    fs.writeFileSync(path.join(BUILD, "last_output.txt"), out);
  } finally { await browser.close(); srv.close(); }
})().catch((e) => { console.error("\n[render] ERRO:", e.message); process.exit(1); });
