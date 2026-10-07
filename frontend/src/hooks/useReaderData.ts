import { useEffect, useRef, useState } from "react";
import { api, type Paper, type ReaderManifest } from "../api";

export function useReaderData(paper: Paper, page: number, totalPages: number, onPaperChange: (paper: Paper) => void) {
  const [manifest, setManifest] = useState<ReaderManifest | null>(null);
  const [manifestError, setManifestError] = useState<string | null>(null);
  const progressRequestRef = useRef(0);
  useEffect(() => {
    let alive = true;
    setManifestError(null);
    api.getReaderManifest(paper.id).then((value) => { if (!alive) return; setManifest(value); if (value.error && !paper.local_pdf_path) setManifestError(value.error); }).catch((reason) => { if (alive) setManifestError(reason instanceof Error ? reason.message : String(reason)); });
    return () => { alive = false; };
  }, [paper.id, paper.local_pdf_path]);
  useEffect(() => {
    if (!totalPages || !paper.id) return;
    const requestId = ++progressRequestRef.current;
    const timer = window.setTimeout(async () => {
      try {
        const progress = Math.round((page / totalPages) * 1000) / 10;
        const updated = await api.updateMetadata(paper.id, { current_page: page, total_pages: totalPages, reading_progress: progress, read_status: page >= totalPages ? "read" : "reading", document_version: manifest?.document_version || paper.document_version || null, last_read_at: new Date().toISOString() });
        if (requestId === progressRequestRef.current && updated[0]) onPaperChange(updated[0]);
      } catch { /* reader progress must not break reading */ }
    }, 500);
    return () => { window.clearTimeout(timer); if (requestId === progressRequestRef.current) progressRequestRef.current += 1; };
  }, [page, totalPages, manifest?.document_version, paper.id]);
  return { manifest, manifestError };
}
