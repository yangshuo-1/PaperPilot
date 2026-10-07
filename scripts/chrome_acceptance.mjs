import fs from "node:fs";

const baseUrl = "http://127.0.0.1:5173";
const paperId = "qwen3-vl-2511-21631";
const apiBaseUrl = "http://127.0.0.1:8020";
const pages = await (await fetch("http://127.0.0.1:9222/json/list")).json();
const page = pages.find((item) => item.type === "page" && item.url.startsWith(baseUrl));
if (!page) throw new Error("No Chrome page target found");

const socket = new WebSocket(page.webSocketDebuggerUrl);
let sequence = 0;
const pending = new Map();
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message);
    pending.delete(message.id);
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

async function waitFor(expression, timeout = 15000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out: ${expression}`);
}

async function navigate(url) {
  const separator = url.includes("?") ? "&" : "?";
  await send("Page.navigate", { url: `${url}${separator}acceptance=${Date.now()}` });
  await new Promise((resolve) => setTimeout(resolve, 900));
}

async function setInput(selector, value) {
  return evaluate(`(() => {
    const input = document.querySelector(${JSON.stringify(selector)});
    if (!input) return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(input, ${JSON.stringify(value)});
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  })()`);
}

async function setTextarea(selector, value) {
  return evaluate(`(() => {
    const input = document.querySelector(${JSON.stringify(selector)});
    if (!input) return false;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
    setter.call(input, ${JSON.stringify(value)});
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  })()`);
}

async function clickText(text) {
  return evaluate(`(() => {
    const node = Array.from(document.querySelectorAll("button")).find((item) => item.textContent.trim() === ${JSON.stringify(text)});
    if (!node) return false;
    node.click();
    return true;
  })()`);
}

async function clickProject(name) {
  return evaluate(`(() => {
    const node = Array.from(document.querySelectorAll("button.projectRow")).find((item) => item.textContent.includes(${JSON.stringify(name)}));
    if (!node) return false;
    node.click();
    return true;
  })()`);
}

await send("Runtime.enable");
await send("Page.enable");
const originalPaper = await (await fetch(`${apiBaseUrl}/api/papers/${paperId}`)).json();
await navigate(`${baseUrl}/papers/${paperId}`);
await waitFor(`document.querySelectorAll(".pdfTextLayer span").length > 0`);
if (!(await evaluate(`Boolean(document.querySelector("#paper-search"))`))) {
  await evaluate(`(() => {
    const button = Array.from(document.querySelectorAll("button")).find((item) => item.textContent.trim().startsWith("搜索"));
    button?.click();
    return Boolean(button);
  })()`);
  await waitFor(`Boolean(document.querySelector("#paper-search"))`);
}
const paperState = await evaluate(`({
  pageCount: document.querySelector(".pageCount")?.textContent?.trim(),
  hasSearch: Boolean(document.querySelector("#paper-search")),
  hasAi: document.body.innerText.includes("论文内 AI"),
  hasNotes: document.body.textContent.includes("Highlights & Notes")
})`);

await setInput("#paper-search", "DeepStack");
await evaluate("document.querySelector('#paper-search').form.requestSubmit()");
await waitFor(`document.querySelectorAll(".paperSearchResult").length >= 2`);
const searchState = await evaluate(`({
  total: document.querySelector(".paperSearchResults")?.innerText || "",
  results: document.querySelectorAll(".paperSearchResult").length
})`);
await evaluate("document.querySelectorAll('.paperSearchResult')[1].click()");
await waitFor(`document.querySelector(".pageInput")?.value === "2"`);
const jumpState = await evaluate(`({ page: document.querySelector(".pageInput")?.value, progress: document.querySelector(".readerProgress")?.textContent?.trim() })`);

// Selection -> highlight -> note is the flow the continuous reader could most
// easily break: page state moved from one global canvas into per-page
// components with their own text layers. Snapshot the annotation ids first and
// remove only the ids this run creates, so a pre-existing user highlight is
// never deleted by a text-match cleanup.
const annotationsUrl = `${apiBaseUrl}/api/papers/${paperId}/annotations`;
const readAnnotationIds = async () => {
  const payload = await (await fetch(annotationsUrl)).json();
  return new Set([
    ...(payload.highlights || []).map((item) => `highlight/${item.id}`),
    ...(payload.notes || []).map((item) => `note/${item.id}`)
  ]);
};
const idsBefore = await readAnnotationIds();
const noteMarker = `CDP 验收笔记 ${Date.now()}`;
let annotationState = { created: false, reason: "not attempted" };
try {
  annotationState = await evaluate(`(() => {
    const pages = Array.from(document.querySelectorAll(".pdfPage"));
    const page = pages.find((node) => node.querySelectorAll(".pdfTextLayer span").length > 2);
    if (!page) return { created: false, reason: "no page with a loaded text layer" };
    const spans = Array.from(page.querySelectorAll(".pdfTextLayer span")).filter((item) => item.textContent?.trim());
    if (spans.length < 2) return { created: false, reason: "fewer than two text spans" };
    const range = document.createRange();
    range.setStart(spans[0], 0);
    range.setEnd(spans[1], spans[1].childNodes.length);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    page.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    return { created: Boolean(selection?.toString().trim()), quote: selection?.toString().trim().slice(0, 48), page: page.dataset.pageNumber };
  })()`);
  if (!annotationState.created) throw new Error(`selection failed: ${annotationState.reason || "empty selection"}`);
  await waitFor(`Boolean(document.querySelector(".annotationActionBar"))`);
  await clickText("创建高亮");
  // The annotation list lives inside a collapsed <details>, so innerText cannot
  // see it; assert on textContent instead of waiting for text that is never rendered.
  await waitFor(`document.body.textContent.includes("高亮 · p.")`);
  await setInput(".noteDraft", noteMarker);
  await clickText("保存笔记");
  await waitFor(`document.body.textContent.includes(${JSON.stringify(noteMarker)})`);
  const idsAfter = await readAnnotationIds();
  const added = [...idsAfter].filter((id) => !idsBefore.has(id));
  annotationState = { ...annotationState, added: added.length, persisted: added.length === 2, visible: await evaluate(`document.querySelectorAll(".annotationItem").length`) };
} finally {
  for (const entry of await readAnnotationIds()) {
    if (idsBefore.has(entry)) continue;
    const [kind, id] = entry.split("/");
    await fetch(`${annotationsUrl}/${kind}/${id}`, { method: "DELETE" });
  }
  await navigate(`${baseUrl}/papers/${paperId}`);
  await waitFor(`document.querySelectorAll(".pdfTextLayer span").length > 0`);
  annotationState = { ...annotationState, leftover: (await readAnnotationIds()).size - idsBefore.size };
}

const paperScreenshot = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync("/tmp/paper-valt-cdp-paper.png", Buffer.from(paperScreenshot.result.data, "base64"));

await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
await navigate(`${baseUrl}/papers/${paperId}`);
await waitFor(`document.querySelectorAll(".pdfTextLayer span").length > 0`);
const mobileState = await evaluate(`({
  width: window.innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth + 1,
  hasReader: Boolean(document.querySelector(".pdfReader"))
})`);
await send("Emulation.clearDeviceMetricsOverride");

await navigate(`${baseUrl}/projects?paper=${paperId}`);
await waitFor(`Boolean(document.querySelector(".projectGrid"))`);
const projectName = `CDP 验收 ${Date.now()}`;
await setInput('input[placeholder="Project 名称"]', projectName);
await setInput('input[placeholder="研究目标（可选）"]', "验证论文到研究工作区的闭环");
await clickText("创建 Project");
await waitFor(`document.body.innerText.includes(${JSON.stringify(projectName)})`);
await clickProject(projectName);
await waitFor(`Boolean(document.querySelector(".projectDetail"))`);
await setInput('input[placeholder="Session 标题"]', "CDP 阅读 Session");
await setInput('input[placeholder="Session 目标（可选）"]', "保存一条研究记录");
await clickText("新建");
await waitFor(`document.body.innerText.includes("CDP 阅读 Session")`);
await setInput('input[placeholder="例如 notes/reading-log.md"]', "notes/cdp-check.md");
await setTextarea(".workspacePanel textarea", "# Chrome CDP 验收\n\n论文搜索与 Project workspace 已验证。\n");
await clickText("创建文件");
await waitFor(`document.body.innerText.includes("notes/cdp-check.md")`);
await evaluate(`(() => {
  const selects = document.querySelectorAll(".resourceForm select");
  const select = selects[2];
  if (!select) return false;
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value").set;
  setter.call(select, ${JSON.stringify(paperId)});
  select.dispatchEvent(new Event("change", { bubbles: true }));
  return true;
})()`);
await clickText("保存关联");
await waitFor(`document.querySelector(".projectDetail")?.innerText.includes("paper 快照")`);
const projectState = await evaluate(`({
  hasSession: document.body.innerText.includes("CDP 阅读 Session"),
  hasWorkspaceFile: document.body.innerText.includes("notes/cdp-check.md"),
  hasPaperLink: document.body.innerText.includes(${JSON.stringify(paperId)}) || document.body.innerText.includes("Qwen3-VL Technical Report"),
  workspaceRoot: document.querySelector(".projectDetail .muted")?.textContent || ""
})`);
const projectScreenshot = await send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync("/tmp/paper-valt-cdp-projects.png", Buffer.from(projectScreenshot.result.data, "base64"));

await evaluate("window.confirm = () => true");
await clickText("删除 Project");
await waitFor(`!document.body.innerText.includes(${JSON.stringify(projectName)})`);
const cleanupState = await evaluate(`({ url: location.href, hasProject: document.body.innerText.includes(${JSON.stringify(projectName)}) })`);
await fetch(`${apiBaseUrl}/api/papers/${paperId}/metadata`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ read_status: originalPaper.read_status, starred: originalPaper.starred, folder_id: originalPaper.folder_id, reading_progress: originalPaper.reading_progress, current_page: originalPaper.current_page, total_pages: originalPaper.total_pages, document_version: originalPaper.document_version, last_read_at: originalPaper.last_read_at }) });
console.log(JSON.stringify({ paperState, searchState, jumpState, annotationState, mobileState, projectState, cleanupState }, null, 2));
socket.close();

// Report a non-zero exit when a checked behaviour did not hold: a script that
// only prints state lets a broken flow pass as "green".
const failures = [];
if (paperState.hasNotes !== true) failures.push("annotation sidebar is missing from the paper page");
if (annotationState.created !== true) failures.push(`annotation selection failed: ${annotationState.reason || "unknown"}`);
if (annotationState.persisted !== true) failures.push(`expected highlight + note to persist, got ${annotationState.added} new annotation(s)`);
if (annotationState.leftover !== 0) failures.push(`acceptance left ${annotationState.leftover} annotation(s) behind`);
if (mobileState.noHorizontalOverflow !== true) failures.push(`mobile horizontal overflow: ${mobileState.scrollWidth} > ${mobileState.width}`);
if (cleanupState.hasProject) failures.push("Project was not deleted");
if (failures.length) {
  console.error(JSON.stringify({ ok: false, failures }, null, 2));
  process.exit(1);
}
console.error(JSON.stringify({ ok: true }));
