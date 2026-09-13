export function cls(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function downloadText(filename: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/plain;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function statusTone(status: string): string {
  if (status === "code_mapped") return "good";
  if (status === "analysis_drafted") return "active";
  if (status === "needs_review") return "warn";
  return "neutral";
}

export function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}
