import fs from "node:fs";

/**
 * Notes acceptance: the full-analysis note must be 图文并茂 with real data.
 *
 *   node scripts/notes_acceptance.mjs
 *
 * Requires FastAPI on :8020, Vite on :5173 and Chrome with
 * --remote-debugging-port=9222. Override the paper with PAPER_ID=…
 *
 * The 2026-10-07 review found that "note tables/formulas/images render" had
 * never been exercised with real data (that note had 0 tables, 0 display
 * formulas, 0 images). This script asserts the actual rendered surfaces —
 * image bytes loaded through the asset API, HTML tables from the paper's
 * LaTeX, KaTeX-typeset display math — and writes screenshots to /tmp for
 * multimodal review. DOM counts alone are not accepted as evidence.
 */

const baseUrl = "http://127.0.0.1:5173";
const paperId = process.env.PAPER_ID || "embeddinggemma-powerful-and-lightweight-text-representations-2509-20354";
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
  const path = `${shotDir}/note-${name}.png`;
  fs.writeFileSync(path, Buffer.from(result.result.data, "base64"));
  return path;
}
async function clickTab(label) {
  await evaluate(`(() => {
    const tab = Array.from(document.querySelectorAll('[role="tab"]')).find((item) => item.textContent.trim() === ${JSON.stringify(label)});
    tab?.click();
    return Boolean(tab);
  })()`);
  await new Promise((resolve) => setTimeout(resolve, 800));
}
/** Scroll the note's own scroll container so `title` starts near the top. */
async function scrollToSection(title) {
  return evaluate(`(() => {
    const heading = Array.from(document.querySelectorAll(".notesPane .markdown h2")).find((node) => node.textContent.includes(${JSON.stringify(title)}));
    if (!heading) return null;
    let node = heading.parentElement;
    let scroller = document.scrollingElement;
    while (node && node !== document.body) {
      const style = getComputedStyle(node);
      if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 4) { scroller = node; break; }
      node = node.parentElement;
    }
    const delta = heading.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
    scroller.scrollTop = scroller.scrollTop + delta - 16;
    return { container: scroller.className || scroller.tagName, top: Math.round(heading.getBoundingClientRect().top) };
  })()`);
}
const failures = [];
function check(name, ok, detail) {
  if (!ok) failures.push({ name, detail });
  return ok;
}
const isHmrNoise = (item) => item.text.includes("[hmr]");
// React Router's v7 future-flag notices are emitted by the app shell, not by
// the note rendering under test; they are identical on every page.
const isKnownShellNoise = (item) => item.text.includes("React Router Future Flag Warning");
const realIssues = () => consoleIssues.filter((item) => !isHmrNoise(item) && !isKnownShellNoise(item));

await send("Runtime.enable");
await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
const artifacts = {};

await send("Page.navigate", { url: `${baseUrl}/papers/${paperId}?notesAcceptance=${Date.now()}` });
await new Promise((resolve) => setTimeout(resolve, 1500));
await clickTab("笔记");
await waitFor(`Boolean(document.querySelector(".notesPane .markdown"))`);
await waitFor(`document.querySelectorAll(".notesPane .markdown img").length > 0`, 25000);
await new Promise((resolve) => setTimeout(resolve, 3000));

const notes = await evaluate(`(() => {
  const pane = document.querySelector(".notesPane");
  const markdown = pane.querySelector(".markdown");
  const images = Array.from(markdown.querySelectorAll("img"));
  const tables = Array.from(markdown.querySelectorAll("table"));
  return {
    tabSelected: Array.from(document.querySelectorAll('[role="tab"]')).some((tab) => tab.getAttribute("aria-selected") === "true" && tab.textContent.trim() === "笔记"),
    images: images.length,
    imagesLoaded: images.filter((img) => img.complete && img.naturalWidth > 0).map((img) => ({ src: img.currentSrc || img.src, w: img.naturalWidth, h: img.naturalHeight })),
    tables: tables.length,
    tableScrollWrappers: markdown.querySelectorAll(".noteTableScroll").length,
    tableMarks: markdown.querySelectorAll(".noteMark").length,
    katexNodes: markdown.querySelectorAll(".katex").length,
    katexDisplay: markdown.querySelectorAll(".katex-display").length,
    literalDoubleDollar: markdown.textContent.includes("$$"),
    // Raw LaTeX is legitimate inside the collapsed "original source" blocks;
    // what must never happen is raw LaTeX leaking into the readable body.
    // KaTeX keeps the TeX source in its MathML annotation, so count only what
    // is neither inside a collapsed source block nor inside a typeset formula.
    latexOutsideFoldedSource: (() => {
      const clone = markdown.cloneNode(true);
      clone.querySelectorAll("details, .katex").forEach((node) => node.remove());
      return (clone.textContent.match(/\\\\begin\{/g) || []).length;
    })(),
    details: markdown.querySelectorAll("details").length,
    sections: Array.from(markdown.querySelectorAll("h2")).map((node) => node.textContent.trim()),
    documentScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    scrollerOverflow: (() => {
      let node = markdown.parentElement;
      while (node && node !== document.body) {
        const style = getComputedStyle(node);
        if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 4) return node.scrollWidth - node.clientWidth;
        node = node.parentElement;
      }
      return 0;
    })()
  };
})()`);
artifacts.notes = notes;
check("笔记标签页处于选中状态", notes.tabSelected === true, JSON.stringify(notes.tabSelected));
check("笔记内嵌论文图片", notes.images >= 1, `images=${notes.images}`);
check("图片确实加载成功（走资产接口）", notes.imagesLoaded.length >= 1, JSON.stringify(notes.imagesLoaded));
check("图片地址来自受限资产接口", notes.imagesLoaded.every((img) => img.src.includes("/reading/asset/")), JSON.stringify(notes.imagesLoaded));
check("笔记含真实表格", notes.tables >= 5, `tables=${notes.tables}`);
check("宽表用滚动容器而不是撑破页面", notes.tableScrollWrappers >= 5, `wrappers=${notes.tableScrollWrappers}`);
check("表格保留加粗/高亮标记", notes.tableMarks >= 3, `noteMark=${notes.tableMarks}`);
check("公式已排版为 KaTeX", notes.katexDisplay >= 1 && notes.katexNodes >= 3, `display=${notes.katexDisplay} katex=${notes.katexNodes}`);
check("正文不残留字面 $$ 或未折叠的原始 LaTeX", !notes.literalDoubleDollar && notes.latexOutsideFoldedSource === 0, `$$=${notes.literalDoubleDollar} latexOutsideDetails=${notes.latexOutsideFoldedSource}`);
check("逐字证据保持折叠", notes.details >= 3, `details=${notes.details}`);
check("图表与公式一节位于摘要之后", notes.sections.indexOf("图表与公式") === notes.sections.indexOf("摘要") + 1, notes.sections.slice(0, 5).join(" / "));
check("1440px 无横向溢出", notes.documentScrollWidth <= notes.innerWidth + 1, `${notes.documentScrollWidth} > ${notes.innerWidth}`);
check("笔记滚动容器自身无横向溢出", notes.scrollerOverflow <= 1, `overflow=${notes.scrollerOverflow}`);

const figureView = await scrollToSection("图表与公式");
artifacts.figureView = figureView;
check("目录/正文可定位到图表与公式一节", Boolean(figureView), JSON.stringify(figureView));
await new Promise((resolve) => setTimeout(resolve, 600));
artifacts.figureShot = await shot("figures");

const tableView = await evaluate(`(() => {
  const table = document.querySelector(".notesPane .markdown .noteTableScroll");
  if (!table) return null;
  let node = table.parentElement;
  let scroller = document.scrollingElement;
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 4) { scroller = node; break; }
    node = node.parentElement;
  }
  const delta = table.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
  scroller.scrollTop = scroller.scrollTop + delta - 120;
  return { rows: table.querySelectorAll("tbody tr").length, top: Math.round(table.getBoundingClientRect().top) };
})()`);
artifacts.tableView = tableView;
check("首个转换表格已渲染数据行", Boolean(tableView) && tableView.rows >= 2, JSON.stringify(tableView));
await new Promise((resolve) => setTimeout(resolve, 500));
artifacts.tableShot = await shot("tables");

const formulaView = await evaluate(`(() => {
  const display = document.querySelector(".notesPane .markdown .katex-display");
  if (!display) return null;
  let node = display.parentElement;
  let scroller = document.scrollingElement;
  while (node && node !== document.body) {
    const style = getComputedStyle(node);
    if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight + 4) { scroller = node; break; }
    node = node.parentElement;
  }
  const delta = display.getBoundingClientRect().top - scroller.getBoundingClientRect().top;
  scroller.scrollTop = scroller.scrollTop + delta - 160;
  return Math.round(display.getBoundingClientRect().top);
})()`);
artifacts.formulaView = formulaView;
await new Promise((resolve) => setTimeout(resolve, 500));
artifacts.formulaShot = await shot("formulas");

/* offline export: the exported HTML must inline the figure and keep tables/math */
const exportDir = "/tmp/note-export";
fs.rmSync(exportDir, { recursive: true, force: true });
fs.mkdirSync(exportDir, { recursive: true });
await send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: exportDir, eventsEnabled: true });
const clickedExport = await evaluate(`(() => {
  const button = Array.from(document.querySelectorAll(".notesPane button")).find((node) => node.textContent.trim() === "导出 HTML");
  button?.click();
  return Boolean(button);
})()`);
let exportedPath = null;
for (let attempt = 0; attempt < 40 && !exportedPath; attempt += 1) {
  const files = fs.readdirSync(exportDir);
  exportedPath = files.find((name) => name.endsWith(".html")) || null;
  if (!exportedPath) await new Promise((resolve) => setTimeout(resolve, 250));
}
const exportedHtml = exportedPath ? fs.readFileSync(`${exportDir}/${exportedPath}`, "utf8") : "";
artifacts.exported = {
  clicked: clickedExport,
  file: exportedPath,
  bytes: exportedHtml.length,
  inlinedImages: (exportedHtml.match(/data:image\/png;base64/g) || []).length,
  tables: (exportedHtml.match(/class="noteTable"/g) || []).length,
  katex: exportedHtml.includes("katex"),
  details: (exportedHtml.match(/<details>/g) || []).length
};
check("导出 HTML 成功生成文件", Boolean(exportedPath), JSON.stringify(artifacts.exported));
check("导出 HTML 内联论文图片（离线可见）", artifacts.exported.inlinedImages >= 1, JSON.stringify(artifacts.exported));
check("导出 HTML 保留表格与公式", artifacts.exported.tables >= 5 && artifacts.exported.katex === true, JSON.stringify(artifacts.exported));

const fallback = await evaluate(`(() => {
  const details = Array.from(document.querySelectorAll(".notesPane .markdown details"));
  const withLatex = details.filter((node) => node.textContent.includes("tabular") || node.textContent.includes("rotatebox"));
  return { details: details.length, fallback: withLatex.length };
})()`);
artifacts.fallback = fallback;
check("无法装配的表格保留原始 LaTeX 折叠块", fallback.fallback >= 1, JSON.stringify(fallback));

/* mobile viewport: wide tables must scroll inside their wrapper, not the page */
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
await new Promise((resolve) => setTimeout(resolve, 1200));
const mobile = await evaluate(`(() => {
  const markdown = document.querySelector(".notesPane .markdown");
  const wrapper = markdown.querySelector(".noteTableScroll");
  return {
    documentScrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    wrapperScrollable: wrapper ? wrapper.scrollWidth > wrapper.clientWidth + 1 : false
  };
})()`);
artifacts.mobile = mobile;
check("移动端页面无横向溢出", mobile.documentScrollWidth <= mobile.innerWidth + 1, `${mobile.documentScrollWidth} > ${mobile.innerWidth}`);
check("移动端宽表在容器内横向滚动", mobile.wrapperScrollable === true, `scrollable=${mobile.wrapperScrollable}`);
artifacts.mobileShot = await shot("mobile");
await send("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

artifacts.consoleIssues = realIssues();
check("控制台无错误与警告", realIssues().length === 0, JSON.stringify(realIssues().slice(0, 4)));

console.log(JSON.stringify({ paperId, artifacts, failures }, null, 2));
socket.close();
if (failures.length) {
  console.error(`\n${failures.length} check(s) failed`);
  process.exit(1);
}
console.log("\nall note rendering checks passed");
