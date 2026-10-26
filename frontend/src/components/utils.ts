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

const dateFormatter = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
const dateTimeFormatter = new Intl.DateTimeFormat("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** Format an ISO timestamp without hardcoding a locale-specific pattern. */
export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
}

export function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTimeFormatter.format(date);
}

/** Scroll behaviour for programmatic scrolling: respect reduced-motion. */
export function scrollBehavior(): ScrollBehavior {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
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
