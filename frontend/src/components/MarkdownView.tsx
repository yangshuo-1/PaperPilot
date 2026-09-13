import { useMemo } from "react";

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function inlineMd(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/\*([^*]+)\*/g, "<em>$1</em>").replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
}

function renderMarkdown(content: string): string {
  const lines = escapeHtml(content).split("\n");
  const output: string[] = [];
  let inList = false;
  let inCode = false;
  for (const raw of lines) {
    if (/^\s*```/.test(raw)) { output.push(inCode ? "</pre>" : "<pre>"); inCode = !inCode; continue; }
    if (inCode) { output.push(raw); continue; }
    if (/^#{1,4}\s/.test(raw)) { if (inList) { output.push("</ul>"); inList = false; } const match = raw.match(/^(#{1,4})\s+(.*)$/)!; output.push(`<h${match[1].length}>${inlineMd(match[2])}</h${match[1].length}>`); continue; }
    if (/^\s*>/.test(raw)) { if (inList) { output.push("</ul>"); inList = false; } output.push(`<blockquote>${inlineMd(raw.replace(/^\s*>\s?/, ""))}</blockquote>`); continue; }
    if (/^\s*[-*]\s/.test(raw)) { if (!inList) { output.push("<ul>"); inList = true; } output.push(`<li>${inlineMd(raw.replace(/^\s*[-*]\s/, ""))}</li>`); continue; }
    if (!raw.trim()) { if (inList) { output.push("</ul>"); inList = false; } continue; }
    if (inList) { output.push("</ul>"); inList = false; }
    output.push(`<p>${inlineMd(raw)}</p>`);
  }
  if (inList) output.push("</ul>");
  if (inCode) output.push("</pre>");
  return output.join("\n");
}

export function MarkdownView({ content }: { content: string }) {
  const html = useMemo(() => renderMarkdown(content), [content]);
  return <article className="markdown" dangerouslySetInnerHTML={{ __html: html }} />;
}
