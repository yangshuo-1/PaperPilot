import DOMPurify from "dompurify";
import katex from "katex";
import { marked, type Token, type Tokens } from "marked";
import { useMemo } from "react";
import "katex/dist/katex.min.css";
import katexStyles from "katex/dist/katex.min.css?inline";
import katexMainFont from "katex/dist/fonts/KaTeX_Main-Regular.woff2?inline";

export type MarkdownHeading = { id: string; text: string; level: number };
const MATH_TOKEN = "PV_MATH_TOKEN_";
// One policy for every HTML path that reaches a reader: Markdown rendering,
// offline export and pre-structured reading blocks must not drift apart.
const SANITIZE_POLICY: Parameters<typeof DOMPurify.sanitize>[1] = { USE_PROFILES: { html: true }, ADD_ATTR: ["target", "rel", "id"], FORBID_TAGS: ["style", "script", "iframe", "object", "embed", "form"], FORBID_ATTR: ["style", "onerror", "onclick", "onload"] };

function slugify(value: string, used: Map<string, number>): string {
  const base = value.toLowerCase().trim().replace(/<[^>]+>/g, "").replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "") || "section";
  const count = used.get(base) || 0;
  used.set(base, count + 1);
  return count ? `${base}-${count + 1}` : base;
}
function renderMath(value: string, displayMode: boolean): string {
  try { return katex.renderToString(value, { displayMode, throwOnError: false, strict: "ignore" }); }
  catch { return `<code>${value.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</code>`; }
}
function protectMath(source: string): { markdown: string; math: Map<string, string> } {
  const math = new Map<string, string>(); let index = 0;
  const token = (latex: string, display: boolean) => { const key = `${MATH_TOKEN}${index++}__`; math.set(key, renderMath(latex.trim(), display)); return key; };
  const chunks = source.split(/(```[\s\S]*?```|~~~[\s\S]*?~~~)/g);
  for (let i = 0; i < chunks.length; i += 2) chunks[i] = chunks[i].replace(/\\\[([\s\S]*?)\\\]/g, (_, v: string) => token(v, true)).replace(/\$\$([\s\S]*?)\$\$/g, (_, v: string) => token(v, true)).replace(/\\\((.*?)\\\)/g, (_, v: string) => token(v, false)).replace(/(?<!\\)\$([^\n$]+?)(?<!\\)\$/g, (_, v: string) => token(v, false));
  return { markdown: chunks.join(""), math };
}
function restoreMath(value: string, math: Map<string, string>): string { let result = value; for (const [key, html] of math) result = result.split(key).join(html); return result; }
function textFromToken(token: Token): string {
  if (token.type === "text" || token.type === "codespan") return token.text;
  if ("tokens" in token && Array.isArray(token.tokens)) return token.tokens.map(textFromToken).join("");
  return "raw" in token && typeof token.raw === "string" ? token.raw : "";
}
export function renderMarkdownHtml(content: string): string {
  const { markdown, math } = protectMath(content); const used = new Map<string, number>(); const renderer = new marked.Renderer();
  renderer.heading = ({ tokens, depth }: Tokens.Heading) => { const text = tokens.map(textFromToken).join(""); return `<h${depth} id="${slugify(text, used)}">${renderer.parser.parseInline(tokens)}</h${depth}>`; };
  const raw = marked.parse(markdown, { renderer, gfm: true, breaks: false }) as string;
  const clean = DOMPurify.sanitize(raw, SANITIZE_POLICY);
  return restoreMath(clean, math);
}
/**
 * Render HTML that is already structured — structured reading blocks arrive as
 * ``source_html`` / ``translated_html`` with LaTeX left inline — through the
 * same math and sanitising rules as Markdown. Without this, a paragraph such as
 * ``compress $2\times2$ visual features`` reaches the reader as raw dollar
 * signs instead of typeset maths.
 */
export function renderRichHtml(value: string): string {
  if (!value) return "";
  const { markdown, math } = protectMath(value);
  return restoreMath(DOMPurify.sanitize(markdown, SANITIZE_POLICY), math);
}
export function extractMarkdownToc(content: string): MarkdownHeading[] {
  const { markdown } = protectMath(content); const used = new Map<string, number>();
  return marked.lexer(markdown).filter((token): token is Tokens.Heading => token.type === "heading").map((token) => { const text = token.tokens.map(textFromToken).join(""); return { id: slugify(text, used), text, level: token.depth }; });
}
export function buildOfflineHtml(content: string, title = "Paper notes"): string {
  const safeTitle = title.replace(/[<&>\"]/g, "");
  const embeddedKatex = katexStyles.replace(/url\(fonts\/KaTeX_Main-Regular\.woff2\)/g, `url(${katexMainFont})`).replace(/url\(fonts\/[^)]+\)/g, "");
  return `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${safeTitle}</title><style>${embeddedKatex}${offlineStyles()}</style></head><body><main class="markdown">${renderMarkdownHtml(content)}</main></body></html>`;
}
export async function buildOfflineHtmlWithAssets(content: string, title = "Paper notes", resolveAsset: (source: string) => Promise<string>): Promise<string> {
  const html = buildOfflineHtml(content, title);
  const parser = new DOMParser();
  const documentRef = parser.parseFromString(html, "text/html");
  await Promise.all(Array.from(documentRef.images).map(async (image) => {
    const source = image.getAttribute("src");
    if (!source || /^data:/i.test(source)) return;
    try { image.src = await resolveAsset(source); } catch { image.setAttribute("data-export-warning", "resource-unavailable"); }
  }));
  return `<!doctype html>${documentRef.documentElement.outerHTML}`;
}
function offlineStyles(): string { return ".markdown{max-width:980px;margin:0 auto;padding:40px 48px;color:#25231e;font:16px/1.75 system-ui,sans-serif}.markdown h1,.markdown h2,.markdown h3,.markdown h4{font-family:Georgia,serif;line-height:1.25;margin:2em 0 .65em}.markdown h1{font-size:2em}.markdown h2{font-size:1.5em}.markdown p{margin:0 0 1em}.markdown blockquote{margin:1em 0;padding:.5em 1em;border-left:4px solid #bd633f;background:#f8f2e9}.markdown pre{overflow:auto;padding:1em;border-radius:8px;background:#f0eee8}.markdown code{padding:.1em .3em;border-radius:4px;background:#f0eee8}.markdown table{width:100%;border-collapse:collapse;margin:1em 0}.markdown th,.markdown td{padding:.5em .7em;border:1px solid #d5d0c5;text-align:left}.markdown img{max-width:100%;height:auto}.katex-display{overflow:auto;padding:.3em 0}"; }
export function MarkdownView({ content, className = "" }: { content: string; className?: string }) { const html = useMemo(() => renderMarkdownHtml(content), [content]); return <article className={`markdown ${className}`.trim()} dangerouslySetInnerHTML={{ __html: html }} />; }
