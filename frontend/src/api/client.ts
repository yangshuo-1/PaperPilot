export const API_BASE_URL = (import.meta.env.VITE_PAPER_VAULT_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(message: string, status: number, body = "") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function resolveApiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path}`;
}

function errorMessage(body: string, fallback: string): string {
  if (!body) return fallback;
  try {
    const parsed: unknown = JSON.parse(body);
    if (typeof parsed === "object" && parsed !== null && "detail" in parsed) {
      const detail = (parsed as { detail?: unknown }).detail;
      if (typeof detail === "string") return detail;
    }
  } catch {
    // Preserve the raw response when it is not JSON.
  }
  return body;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(errorMessage(body, response.statusText), response.status, body);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function requestText(path: string): Promise<string> {
  const response = await fetch(resolveApiUrl(path));
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(errorMessage(body, response.statusText), response.status, body);
  }
  return response.text();
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}
