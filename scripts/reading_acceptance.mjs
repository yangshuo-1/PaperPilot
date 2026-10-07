import fs from "node:fs";

/**
 * Reading-workspace acceptance: the four things the reader complained about.
 *
 *   node scripts/reading_acceptance.mjs
 *
 * Requires the FastAPI server on :8020, Vite on :5173 and Chrome with
 * --remote-debugging-port=9222. Writes screenshots to /tmp and prints a JSON
 * report; it fails loudly when an assertion does not hold, because "the page
 * loaded" is not evidence that the reading surface is usable.
 */

const baseUrl = "http://127.0.0.1:5173";
const apiBaseUrl = "http://127.0.0.1:8020";
const paperId = process.env.PAPER_ID || "qwen3-vl-2511-21631";
const shotDir = process.env.SHOT_DIR || "/tmp";

const pages = await (await fetch("http://127.0.0.1:9222/json/list")).json();
const target = pages.find((item) => item.type === "page" && item.url.startsWith(baseUrl)) || pages.find((item) => item.type === "page");
if (!target) throw new Error("No Chrome page target found on :9222");

const socket = new WebSocket(target.webSocketDebuggerUrl);
let sequence = 0;
const pending = new Map();
const consoleIssues = [];
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
  }
  if (message.method === "Runtime.consoleAPICalled" && ["error", "warning"].includes(message.params.type)) {
    consoleIssues.push({ level: message.params.type, text: (message.params.args || []).map((arg) => arg.value ?? arg.description ?? "").join(" ").slice(0, 300) });
  }
  if (message.method === "Runtime.exceptionThrown") {
    consoleIssues.push({ level: "exception", text: message.params.exceptionDetails?.exception?.description?.slice(0, 300) || "exception" });
  }
};
await new Promise((resolve, reject) => {
  socket.onopen = resolve;
  socket.onerror = reject;
});
function send(method, params = {}) {
  return new Promise((resolve) => {
    const id = ++sequence;
    pending.set(id, resolve);
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
  if (result.result?.exceptionDetails) throw new Error(result.result.exceptionDetails.exception?.description || "Runtime evaluation failed");
  return result.result?.result?.value;
}
async function waitFor(expression, timeout = 20000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out: ${expression}`);
}
async function shot(name) {
  const result = await send("Page.captureScreenshot", { format: "png" });
  const path = `${shotDir}/reading-${name}.png`;
  fs.writeFileSync(path, Buffer.from(result.result.data, "base64"));
  return path;
}
async function navigate(url) {
  await send("Page.navigate", { url: `${url}${url.includes("?") ? "&" : "?"}acceptance=${Date.now()}` });
  await new Promise((resolve) => setTimeout(resolve, 1200));
}
async function clickTab(label) {
  await evaluate(`(() => {
    const tab = Array.from(document.querySelectorAll('[role="tab"]')).find((item) => item.textContent.trim() === ${JSON.stringify(label)});
    tab?.click();
    return Boolean(tab);
  })()`);
  await new Promise((resolve) => setTimeout(resolve, 800));
}
const failures = [];
function check(name, ok, detail) {
  if (!ok) failures.push({ name, detail });
  return ok;
}
// Dev-server HMR messages describe an edit that happened while this script was
// running, not a defect in the loaded page; the production build is verified
// separately by `npm run build`.
const isHmrNoise = (item) => item.text.includes("[hmr]");
const realIssues = () => consoleIssues.filter((item) => !isHmrNoise(item));

await send("Runtime.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const artifacts = {};

/* ---------------------------------------------------------------- PDF (R4) */
await navigate(`${baseUrl}/papers/${paperId}`);
await waitFor(`document.querySelectorAll(".pdfTextLayer span").length > 0`);
const pdfInitial = await evaluate(`({
  pages: document.querySelectorAll(".pdfPageSlot").length,
  renderedPages: document.querySelectorAll(".pdfPage.isActive canvas").length,
  pageLabel: document.querySelector(".readerProgress")?.textContent?.trim(),
  viewportHeight: document.querySelector(".paperModeViewport")?.clientHeight || 0,
  contentHeight: document.querySelector(".pdfStage")?.clientHeight || 0,
  stageWidth: document.querySelector(".pdfStage")?.clientWidth || 0,
  pageWidth: Math.round(document.querySelector(".pdfPage.isActive")?.getBoundingClientRect().width || 0),
  scrollWidth: document.documentElement.scrollWidth,
  innerWidth: window.innerWidth,
  innerHeight: window.innerHeight,
  windowScrollY: window.scrollY,
  titleTop: Math.round(document.querySelector(".paperHeader h1")?.getBoundingClientRect().top ?? -999)
})`);
artifacts.pdfInitial = pdfInitial;
check("PDF 渲染多页槽位（连续阅读）", pdfInitial.pages >= 3, `pages=${pdfInitial.pages}`);
check("PDF 只渲染视口附近页面", pdfInitial.renderedPages > 0 && pdfInitial.renderedPages <= 12, `activeCanvases=${pdfInitial.renderedPages}`);
check("PDF 页面利用宽度（>900px）", pdfInitial.pageWidth > 900, `pageWidth=${pdfInitial.pageWidth} stage=${pdfInitial.stageWidth}`);
check("1440px 无横向溢出", pdfInitial.scrollWidth <= pdfInitial.innerWidth + 1, `${pdfInitial.scrollWidth} > ${pdfInitial.innerWidth}`);
check("主内容视口占可视高度 ≥75%", pdfInitial.viewportHeight / pdfInitial.innerHeight >= 0.75, `${pdfInitial.viewportHeight}/${pdfInitial.innerHeight}`);
check("打开论文后窗口没有被阅读器内部滚动带偏", pdfInitial.windowScrollY === 0 && pdfInitial.titleTop >= 0, `scrollY=${pdfInitial.windowScrollY} titleTop=${pdfInitial.titleTop}`);
await evaluate(`(() => { const stage = document.querySelector(".pdfStage"); stage.scrollTop = stage.scrollHeight * 0.25; return true; })()`);
await new Promise((resolve) => setTimeout(resolve, 1500));
const pdfScrolled = await evaluate(`({ page: Number(document.querySelector(".pageInput")?.value || 0), rendered: document.querySelectorAll(".pdfPage.isActive canvas").length, windowScrollY: window.scrollY, titleTop: Math.round(document.querySelector(".paperHeader h1")?.getBoundingClientRect().top ?? -999) })`);
artifacts.pdfScrolled = pdfScrolled;
check("连续滚动后页码自动前进", pdfScrolled.page > 1, `page=${pdfScrolled.page}`);
check("滚动后仍只保留少量 canvas", pdfScrolled.rendered <= 12, `activeCanvases=${pdfScrolled.rendered}`);
check("连续滚动不牵动窗口滚动", pdfScrolled.windowScrollY === 0 && pdfScrolled.titleTop >= 0, `scrollY=${pdfScrolled.windowScrollY} titleTop=${pdfScrolled.titleTop}`);
await evaluate(`(() => { const input = document.querySelector(".pageInput"); const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set; setter.call(input, "20"); input.dispatchEvent(new Event("input", { bubbles: true })); return true; })()`);
await new Promise((resolve) => setTimeout(resolve, 1500));
const pdfJumped = await evaluate(`({ page: Number(document.querySelector(".pageInput")?.value || 0), windowScrollY: window.scrollY, titleTop: Math.round(document.querySelector(".paperHeader h1")?.getBoundingClientRect().top ?? -999) })`);
artifacts.pdfJumped = pdfJumped;
check("跳页后窗口与标题仍在原位", pdfJumped.windowScrollY === 0 && pdfJumped.titleTop >= 0, `page=${pdfJumped.page} scrollY=${pdfJumped.windowScrollY} titleTop=${pdfJumped.titleTop}`);
// Fast scrolling is what cancels in-flight page renders; an abandoned promise
// here used to surface as "Uncaught (in promise) RenderingCancelledException".
const fastScrollMark = consoleIssues.length;
await evaluate(`(async () => {
  const stage = document.querySelector(".pdfStage");
  for (let step = 0; step < 12; step += 1) { stage.scrollTop = stage.scrollHeight * (step / 12); await new Promise((resolve) => setTimeout(resolve, 120)); }
  await new Promise((resolve) => setTimeout(resolve, 1200));
  return true;
})()`);
const fastScrollIssues = consoleIssues.slice(fastScrollMark).filter((item) => item.level !== "warning");
artifacts.fastScroll = { issues: fastScrollIssues.length, sample: fastScrollIssues.slice(0, 3).map((item) => item.text.slice(0, 80)) };
check("快速滚动不产生未捕获异常", fastScrollIssues.length === 0, `${fastScrollIssues.length} exceptions: ${fastScrollIssues[0]?.text || ""}`);
artifacts.pdfShot = await shot("pdf");

/* ----------------------------------------------------------- 译文对照 (R5) */
await clickTab("译文");
await waitFor(`Boolean(document.querySelector(".parallelReading .parallelColumns"))`, 30000);
const parallel = await evaluate(`(() => {
  const columns = document.querySelectorAll(".parallelColumn");
  const left = columns[0], right = columns[1];
  const katexAll = document.querySelectorAll(".parallelReading .katex").length;
  const katexLeft = left ? left.querySelectorAll(".katex").length : 0;
  const katexRight = right ? right.querySelectorAll(".katex").length : 0;
  const rawDollar = Array.from(document.querySelectorAll(".parallelReading .parallelBlockHtml")).filter((node) => /\\$[^$\\n]{1,60}\\$/.test(node.textContent || "")).length;
  const blocks = document.querySelectorAll(".parallelTranslated [data-block-id]").length;
  return {
    katexAll, katexLeft, katexRight, rawDollar,
    blocks, leftScrollHeight: left?.scrollHeight || 0, rightScrollHeight: right?.scrollHeight || 0,
    sectionLabels: document.querySelectorAll(".parallelSection").length,
    pageButtons: document.querySelectorAll(".parallelBlockMeta button").length,
    assetImages: document.querySelectorAll(".parallelAsset").length,
    tables: document.querySelectorAll(".parallelReading table").length
  };
})()`);
artifacts.parallel = parallel;
check("译文对照是左右两栏", parallel.blocks > 100, `translatedBlocks=${parallel.blocks}`);
check("原文栏公式已排版（KaTeX，非字面 $）", parallel.katexLeft > 0, `katexLeft=${parallel.katexLeft}`);
check("对照视图不再出现裸 $ 公式", parallel.rawDollar === 0, `blocksWithRawDollar=${parallel.rawDollar}`);
check("表格结构保留", parallel.tables >= 10, `tables=${parallel.tables}`);
check("图表资产保留", parallel.assetImages >= 3, `images=${parallel.assetImages}`);
check("tier1 显示章节定位", parallel.sectionLabels > 0, `sectionLabels=${parallel.sectionLabels}`);
artifacts.parallelShot = await shot("parallel");

const sync = await evaluate(`(async () => {
  const columns = document.querySelectorAll(".parallelColumn");
  const left = columns[0], right = columns[1];
  const beforeRight = right.scrollTop;
  left.scrollTop = left.scrollHeight * 0.4;
  left.dispatchEvent(new Event("scroll", { bubbles: true }));
  await new Promise((resolve) => setTimeout(resolve, 400));
  const anchorLeft = (() => {
    const nodes = left.querySelectorAll("[data-block-id]");
    const top = left.getBoundingClientRect().top;
    let current = nodes[0];
    for (const node of nodes) { if (node.getBoundingClientRect().top - top > 1) break; current = node; }
    return current;
  })();
  const counterpart = right.querySelector('[data-block-id="' + anchorLeft.dataset.blockId + '"]');
  return {
    moved: right.scrollTop > beforeRight + 50,
    id: anchorLeft.dataset.blockId,
    drift: counterpart ? Math.round(Math.abs(counterpart.getBoundingClientRect().top - anchorLeft.getBoundingClientRect().top)) : null
  };
})()`);
artifacts.syncScroll = sync;
check("同步滚动按块锚点生效", sync.moved === true, `moved=${sync.moved}`);
check("同步后对应块对齐（漂移 < 24px）", sync.drift !== null && sync.drift < 24, `drift=${sync.drift}`);

/* ------------------------------------------------------------- 笔记 (R2) */
await clickTab("笔记");
await waitFor(`Boolean(document.querySelector(".notesPane .markdown"))`);
const notes = await evaluate(`({
  toc: document.querySelectorAll(".notesToc a").length,
  headings: document.querySelectorAll(".notesPane .markdown h1, .notesPane .markdown h2, .notesPane .markdown h3").length,
  documents: document.querySelectorAll(".notesDocuments .miniTag").length,
  distinctTitles: new Set(Array.from(document.querySelectorAll(".notesDocuments .miniTag")).map((node) => node.textContent.trim())).size,
  hasExport: document.body.innerText.includes("导出 HTML"),
  katex: document.querySelectorAll(".notesPane .katex").length,
  bodyWidth: Math.round(document.querySelector(".notesBody .markdown")?.getBoundingClientRect().width || 0)
})`);
artifacts.notes = notes;
check("笔记文档标题可区分（无重复 key 来源）", notes.documents === notes.distinctTitles, `${notes.documents} docs / ${notes.distinctTitles} titles`);
check("笔记正文宽度利用宽屏（>900px）", notes.bodyWidth > 900, `width=${notes.bodyWidth}`);
artifacts.notesShot = await shot("notes");

/* ------------------------------------------------------------- 图解 (R3) */
await clickTab("图解");
await waitFor(`Boolean(document.querySelector(".diagramFrame"))`, 30000);
await new Promise((resolve) => setTimeout(resolve, 2500));
const diagram = await evaluate(`(async () => {
  const frame = document.querySelector(".diagramFrame");
  const canvas = frame?.contentDocument?.querySelector(".canvas");
  const before = canvas?.style.transform || "";
  const readScale = () => {
    const value = /scale\\(([0-9.]+)\\)/.exec(canvas?.style.transform || "");
    return value ? Number(value[1]) : null;
  };
  const readerScale = readScale();
  const buttons = Array.from(document.querySelectorAll(".diagramViewerToolbar button"));
  const zoomIn = buttons.find((item) => item.textContent.trim() === "＋");
  zoomIn?.click();
  await new Promise((resolve) => setTimeout(resolve, 500));
  const afterZoom = readScale();
  const fit = buttons.find((item) => item.textContent.trim() === "适应宽度");
  fit?.click();
  await new Promise((resolve) => setTimeout(resolve, 500));
  return {
    generator: frame?.contentDocument?.querySelector('meta[name="generator"]')?.getAttribute("content") || null,
    canvasWidth: canvas?.offsetWidth || 0,
    iframeWidth: Math.round(frame?.getBoundingClientRect().width || 0),
    readerScale, afterZoom, afterFit: readScale(),
    sizerLeft: Math.round(frame?.contentDocument?.querySelector(".sizer")?.getBoundingClientRect().left - frame?.contentDocument?.querySelector(".viewport")?.getBoundingClientRect().left || 0),
    listensForViewport: (frame?.contentDocument?.documentElement?.innerHTML || "").includes("paper-vault-diagram-viewport"),
    toolbarButtons: buttons.map((item) => item.textContent.trim())
  };
})()`);
artifacts.diagram = diagram;
check("图解产物由当前渲染器生成", diagram.generator === "diagram.render.v3", `generator=${diagram.generator}`);
check("图解 HTML 接受前端视口指令", diagram.listensForViewport === true, "postMessage listener missing");
check("缩放按钮实际改变图形比例", diagram.afterZoom !== null && diagram.afterZoom > (diagram.readerScale ?? 0), `before=${diagram.readerScale} after=${diagram.afterZoom}`);
check("适应宽度按 iframe 宽度计算（不被高度挤小）", (diagram.afterFit ?? 0) > 0.5, `fitScale=${diagram.afterFit} canvas=${diagram.canvasWidth} iframe=${diagram.iframeWidth}`);
check("图形比画框窄时水平居中", diagram.canvasWidth >= diagram.iframeWidth || diagram.sizerLeft > 0, `sizerLeft=${diagram.sizerLeft} canvas=${diagram.canvasWidth} iframe=${diagram.iframeWidth}`);
artifacts.diagramShot = await shot("diagram");

/* ------------------------------------------------------- 移动端 + 控制台 */
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
await navigate(`${baseUrl}/papers/${paperId}`);
await waitFor(`document.querySelectorAll(".pdfTextLayer span").length > 0`);
await clickTab("译文");
await waitFor(`Boolean(document.querySelector(".parallelMobileBlocks"))`, 30000);
const mobile = await evaluate(`({
  width: window.innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
  mobilePairs: document.querySelectorAll(".parallelMobilePair").length,
  desktopColumns: document.querySelectorAll(".parallelColumns").length
})`);
artifacts.mobile = mobile;
check("移动端逐块对照渲染", mobile.mobilePairs > 100 && mobile.desktopColumns === 0, `pairs=${mobile.mobilePairs} desktop=${mobile.desktopColumns}`);
check("移动端无横向溢出", mobile.noHorizontalOverflow === true, `${mobile.scrollWidth} > ${mobile.width}`);
artifacts.mobileShot = await shot("mobile");
await send("Emulation.clearDeviceMetricsOverride");

const duplicateKeys = consoleIssues.filter((item) => /same key|duplicate key|unique "key"/i.test(item.text));
const errors = realIssues().filter((item) => item.level !== "warning");
artifacts.console = { total: consoleIssues.length, hmrNoise: consoleIssues.filter(isHmrNoise).length, errors: errors.length, duplicateKeys: duplicateKeys.length, sample: errors.slice(0, 5).map((item) => item.text.slice(0, 160)) };
check("无 React 重复 key 警告", duplicateKeys.length === 0, `${duplicateKeys.length} warnings`);
check("无控制台错误", errors.length === 0, `${errors.length} errors`);

console.log(JSON.stringify({ ok: failures.length === 0, failures, artifacts }, null, 2));
socket.close();
process.exit(failures.length === 0 ? 0 : 1);
