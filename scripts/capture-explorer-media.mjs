#!/usr/bin/env node
/* Regenerate the explorer's documentation media with the browser already on
 * the machine. Zero npm dependencies: Edge/Chrome is driven over the DevTools
 * protocol; ffmpeg turns the captured screencast into MP4 + GIF.
 *
 * Start the explorer first, then:
 *   node scripts/capture-explorer-media.mjs --base http://127.0.0.1:8766 --scenario hero
 *   node scripts/capture-explorer-media.mjs --base http://127.0.0.1:8766 --scenario timeline
 *   node scripts/capture-explorer-media.mjs --base http://127.0.0.1:8766 --scenario metrics
 *   node scripts/capture-explorer-media.mjs --base http://127.0.0.1:8766 --scenario video
 *   node scripts/capture-explorer-media.mjs --base http://127.0.0.1:8767 --scenario fallback --session ses_ee839702
 *
 * Scenarios: hero, timeline, metrics, fallback, video, all.
 * --out      directory for PNG stills     (default docs/screenshots)
 * --media    directory for MP4/GIF        (default docs/media)
 * --port     DevTools port                (default 9333)
 * --session  session id fragment to pick  (optional)
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as sleep } from "node:timers/promises";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");

const argv = process.argv.slice(2);
function arg(name, fallback = null) {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
}

const base = arg("base", "http://127.0.0.1:8766").replace(/\/$/, "");
const scenario = arg("scenario", "all");
const outDir = resolve(ROOT, arg("out", "docs/screenshots"));
const mediaDir = resolve(ROOT, arg("media", "docs/media"));
const sessionFragment = arg("session", "");
const devtoolsPort = Number(arg("port", "9333"));
const width = 1600;
const height = 1000;
const edgePath =
  process.env.EDGE_PATH ||
  (process.platform === "win32"
    ? "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
    : "msedge");
const ffmpegPath = process.env.FFMPEG_PATH || "ffmpeg";

if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
if (!existsSync(mediaDir)) mkdirSync(mediaDir, { recursive: true });

const profileDir = mkdtempSync(join(tmpdir(), "agent-causality-capture-"));
const browser = spawn(
  edgePath,
  [
    "--headless=new",
    "--disable-gpu",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    `--remote-debugging-port=${devtoolsPort}`,
    `--user-data-dir=${profileDir}`,
    `--window-size=${width},${height}`,
    "about:blank",
  ],
  { stdio: "ignore" },
);

let ws;
let nextId = 1;
const pending = new Map();
const listeners = new Map();

function on(method, fn) {
  if (!listeners.has(method)) listeners.set(method, new Set());
  listeners.get(method).add(fn);
}

function send(method, params = {}) {
  const id = nextId++;
  return new Promise((resolvePromise, reject) => {
    pending.set(id, { resolve: resolvePromise, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function evaluate(expression) {
  const result = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  }
  return result.result?.value;
}

async function waitFor(expression, timeout = 20000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return;
    await sleep(200);
  }
  throw new Error(`timed out waiting for ${expression}`);
}

async function connect() {
  const deadline = Date.now() + 20000;
  let targets = null;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${devtoolsPort}/json/list`);
      targets = await response.json();
      const page = targets.find((t) => t.type === "page");
      if (page) break;
    } catch {
      // browser still starting
    }
    await sleep(250);
  }
  const target = targets?.find((t) => t.type === "page");
  if (!target) throw new Error("could not find an Edge DevTools page target");

  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolvePromise, reject) => {
    ws.addEventListener("open", resolvePromise, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve: resolvePromise, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolvePromise(message.result);
      return;
    }
    for (const listener of listeners.get(message.method) ?? []) {
      listener(message.params);
    }
  });
}

async function open() {
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await send("Page.navigate", { url: base });
  await waitFor("!!document.querySelector('#dag .node')", 30000);
  await evaluate("document.fonts.ready.then(() => true)");
  await sleep(600);
}

async function screenshot(path) {
  const result = await send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  });
  writeFileSync(path, Buffer.from(result.data, "base64"));
  console.log("stills:", path);
}

async function clickText(selector, text) {
  const clicked = await evaluate(`(() => {
    const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
      .find((node) => node.textContent.trim() === ${JSON.stringify(text)});
    if (!el) return false;
    el.click();
    return true;
  })()`);
  if (!clicked) throw new Error(`could not find ${selector} with text "${text}"`);
}

async function selectSession(fragment) {
  if (!fragment) return;
  const changed = await evaluate(`(() => {
    const select = document.querySelector('.session-pick select');
    if (!select) return false;
    const option = [...select.options].find(
      (o) => o.value.includes(${JSON.stringify(fragment)}) || o.textContent.includes(${JSON.stringify(fragment)}),
    );
    if (!option) return false;
    select.value = option.value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
  if (!changed) throw new Error(`session not found: ${fragment}`);
  await sleep(800);
}

async function selectToolResult() {
  const clicked = await evaluate(`(() => {
    const nodes = [...document.querySelectorAll('#dag .node')];
    const target = nodes.filter((node) => node.textContent.includes('tool_result')).at(-1)
      ?? nodes.filter((node) => !node.classList.contains('failure')).at(-1);
    if (!target) return false;
    target.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    return true;
  })()`);
  if (clicked) {
    await sleep(900);
    await waitFor("document.querySelector('#event-detail')?.textContent?.includes('COMMAND') || document.querySelector('#event-detail')?.textContent?.includes('TYPE')", 10000).catch(() => {});
  }
}

async function scrollScreen(position) {
  await evaluate(`(() => {
    const screen = document.querySelector('.screen-scroll');
    if (!screen) return;
    screen.scrollTo({ top: ${position}, behavior: 'instant' });
  })()`);
  await sleep(350);
}

async function setView(view) {
  await clickText(".view-toggle button", view);
  await sleep(500);
}

async function injectCursor() {
  await evaluate(`(() => {
    if (document.getElementById('__capture_cursor')) return;
    const style = document.createElement('style');
    style.textContent = \`
      #__capture_cursor { position: fixed; left: 0; top: 0; z-index: 2147483647; width: 16px; height: 22px;
        background: #ffcb78; pointer-events: none;
        clip-path: polygon(0 0, 0 100%, 5px 72%, 9px 100%, 13px 95%, 9px 68%, 16px 68%);
        filter: drop-shadow(0 0 4px rgba(0,0,0,.9)); transition: transform 320ms cubic-bezier(.2,.8,.2,1); }
      #__capture_cursor::after { content: ""; position: absolute; left: -10px; top: -10px; width: 28px; height: 28px;
        border: 1px solid #ffcb78; border-radius: 50%; opacity: 0; }
      #__capture_cursor.is-click::after { animation: __capture_click 420ms ease-out; }
      @keyframes __capture_click { from { transform: scale(.2); opacity: .95; } to { transform: scale(1.7); opacity: 0; } }
    \`;
    document.head.appendChild(style);
    const cursor = document.createElement('div');
    cursor.id = '__capture_cursor';
    cursor.style.transform = 'translate(-100px, -100px)';
    document.body.appendChild(cursor);
  })()`);
}

async function moveCursor(selector, text = null) {
  const point = await evaluate(`(() => {
    const candidates = [...document.querySelectorAll(${JSON.stringify(selector)})];
    const el = ${text === null ? "candidates[0]" : `candidates.find((n) => n.textContent.trim() === ${JSON.stringify(text)})`};
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  if (!point) throw new Error(`cursor target not found: ${selector} ${text ?? ""}`);
  await evaluate(`document.getElementById('__capture_cursor').style.transform = 'translate(${point.x}px, ${point.y}px)'`);
  await sleep(380);
  return point;
}

async function clickAt(point) {
  await evaluate(`document.getElementById('__capture_cursor').classList.add('is-click')`);
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: point.x, y: point.y, button: "none" });
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x: point.x, y: point.y, button: "left", clickCount: 1 });
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x: point.x, y: point.y, button: "left", clickCount: 1 });
  await sleep(180);
  await evaluate(`setTimeout(() => document.getElementById('__capture_cursor')?.classList.remove('is-click'), 420)`);
}

async function captureScreencast() {
  const framesDir = mkdtempSync(join(tmpdir(), "agent-causality-frames-"));
  const frames = [];
  const onFrame = async ({ data, metadata, sessionId }) => {
    const index = frames.length;
    const path = join(framesDir, `frame-${String(index).padStart(4, "0")}.jpg`);
    writeFileSync(path, Buffer.from(data, "base64"));
    frames.push({ path, timestamp: metadata.timestamp });
    await send("Page.screencastFrameAck", { sessionId });
  };
  on("Page.screencastFrame", (params) => {
    onFrame(params).catch((error) => console.error("screencast frame:", error));
  });
  await send("Page.startScreencast", {
    format: "jpeg",
    quality: 88,
    maxWidth: width,
    maxHeight: height,
    everyNthFrame: 1,
  });
  return { framesDir, frames };
}

async function finishVideo(framesDir, frames) {
  await send("Page.stopScreencast");
  await sleep(500);
  if (frames.length < 8) throw new Error(`screencast captured only ${frames.length} frames`);

  const concatFile = join(framesDir, "frames.txt");
  const lines = [];
  for (let i = 0; i < frames.length; i++) {
    const next = frames[i + 1]?.timestamp ?? frames[i].timestamp + 0.1;
    const duration = Math.max(0.04, Math.min(0.5, next - frames[i].timestamp));
    lines.push(`file '${frames[i].path.replaceAll("\\", "/")}'`, `duration ${duration.toFixed(3)}`);
  }
  lines.push(`file '${frames.at(-1).path.replaceAll("\\", "/")}'`);
  writeFileSync(concatFile, lines.join("\n"), "utf8");

  const mp4 = join(mediaDir, "explorer-demo.mp4");
  const gif = join(mediaDir, "explorer-demo.gif");
  const run = (args) =>
    new Promise((resolvePromise, reject) => {
      const child = spawn(ffmpegPath, args, { stdio: "inherit" });
      child.on("error", reject);
      child.on("exit", (code) => (code === 0 ? resolvePromise() : reject(new Error(`ffmpeg exited ${code}`))));
    });

  await run([
    "-y",
    "-f",
    "concat",
    "-safe",
    "0",
    "-i",
    concatFile,
    "-vf",
    "fps=15,scale=1200:-1:flags=lanczos",
    "-c:v",
    "libx264",
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    mp4,
  ]);
  console.log("video:", mp4);
  await run([
    "-y",
    "-i",
    mp4,
    "-vf",
    "fps=12,scale=1200:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
    "-loop",
    "0",
    gif,
  ]);
  console.log("video:", gif);
  console.log("frames:", frames.length);
  rmSync(framesDir, { recursive: true, force: true });
}

async function runVideo() {
  await injectCursor();
  const { framesDir, frames } = await captureScreencast();
  await sleep(1000);

  let point = await moveCursor(".view-toggle button", "Timeline");
  await clickAt(point);
  await waitFor("!!document.querySelector('#timeline .clip')");
  await sleep(1000);

  // Pick the selected/last failure-slice clip for a readable inspector.
  const clip = await evaluate(`(() => {
    const clips = [...document.querySelectorAll('#timeline .clip')];
    const el = clips.find((c) => c.classList.contains('selected')) ?? clips.at(-1);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  if (clip) {
    await evaluate(`document.getElementById('__capture_cursor').style.transform = 'translate(${clip.x}px, ${clip.y}px)'`);
    await sleep(380);
    await clickAt(clip);
    await sleep(1000);
  }

  // Scroll to the analysis tabs, then open Metrics.
  await evaluate(`document.querySelector('.screen-scroll').scrollTo({ top: document.querySelector('.screen-scroll').scrollHeight, behavior: 'smooth' })`);
  await sleep(1100);
  point = await moveCursor(".tabs button", "Metrics");
  await clickAt(point);
  await sleep(1200);

  // Return to the DAG and select one more event.
  await evaluate(`document.querySelector('.screen-scroll').scrollTo({ top: 0, behavior: 'smooth' })`);
  await sleep(1000);
  point = await moveCursor(".view-toggle button", "Graph");
  await clickAt(point);
  await waitFor("!!document.querySelector('#dag .node')");
  await sleep(900);
  const node = await evaluate(`(() => {
    const nodes = [...document.querySelectorAll('#dag .node')].filter((n) => n.textContent.includes('tool_result'));
    const el = nodes.at(-1);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  if (node) {
    await evaluate(`document.getElementById('__capture_cursor').style.transform = 'translate(${node.x}px, ${node.y}px)'`);
    await sleep(380);
    await clickAt(node);
    await sleep(1200);
  }
  await sleep(800);
  await finishVideo(framesDir, frames);
}

async function runStill(name) {
  if (name === "hero") {
    await selectToolResult();
    await scrollScreen(0);
    await screenshot(join(outDir, "explorer-shared-state-fresh.png"));
  } else if (name === "timeline") {
    await selectToolResult();
    await setView("Timeline");
    await waitFor("!!document.querySelector('#timeline .clip')");
    await scrollScreen(0);
    await screenshot(join(outDir, "timeline.png"));
  } else if (name === "metrics") {
    await selectToolResult();
    await setView("Timeline");
    await waitFor("!!document.querySelector('#timeline .clip')");
    await evaluate(`document.querySelector('.screen-scroll').scrollTo({ top: document.querySelector('.screen-scroll').scrollHeight, behavior: 'instant' })`);
    await sleep(300);
    await clickText(".tabs button", "Metrics");
    await sleep(500);
    await screenshot(join(outDir, "explorer-timeline-metrics.png"));
  } else if (name === "fallback") {
    await selectSession(sessionFragment);
    await selectToolResult();
    await setView("Graph");
    await scrollScreen(0);
    await screenshot(join(outDir, "explorer-graph-fallback.png"));
  }
}

try {
  await connect();
  await open();
  const wanted = scenario === "all" ? ["hero", "timeline", "metrics", "fallback", "video"] : [scenario];
  for (const name of wanted) {
    if (name === "video") {
      await open();
      await runVideo();
    } else {
      await open();
      await runStill(name);
    }
  }
} finally {
  try {
    ws?.close();
  } catch {}
  browser.kill();
  await sleep(500);
  rmSync(profileDir, { recursive: true, force: true });
}
