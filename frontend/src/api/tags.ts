import { request } from "./client";
import type { Paper } from "./papers";

export const updateTags = (paperId: string, tags: string[]) => request<Paper>(`/api/papers/${paperId}/tags`, {
  method: "PUT",
  body: JSON.stringify({ tags }),
});
