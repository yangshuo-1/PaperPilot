import { request } from "./client";

export type Folder = { id: string; name: string; parent_id?: string | null; order: number };
export type FolderListResponse = { version: number; folders: Folder[] };
export const listFolders = () => request<FolderListResponse>("/api/papers/folders");
export const createFolder = (name: string, parentId: string | null = null) => request<Folder>("/api/papers/folders", { method: "POST", body: JSON.stringify({ name, parent_id: parentId }) });
export const updateFolder = (folderId: string, fields: { name?: string; parent_id?: string | null }) => request<Folder>(`/api/papers/folders/${folderId}`, { method: "PUT", body: JSON.stringify(fields) });
export const deleteFolder = (folderId: string) => request<void>(`/api/papers/folders/${folderId}`, { method: "DELETE" });
