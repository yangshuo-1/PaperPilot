import { useCallback } from "react";
import { api, type Paper, type ReadStatus } from "../api";

export function usePaperMutations(paper: Paper, onChange: (paper: Paper) => void) {
  const toggleStar = useCallback(async () => {
    const updated = await api.updateMetadata(paper.id, { starred: !paper.starred });
    onChange(updated[0] ?? paper);
  }, [onChange, paper]);
  const setReadStatus = useCallback(async (status: ReadStatus) => {
    const updated = await api.updateMetadata(paper.id, { read_status: status });
    onChange(updated[0] ?? paper);
  }, [onChange, paper]);
  const addTag = useCallback(async (tag: string) => {
    const updated = await api.updateTags(paper.id, [...paper.tags, tag]);
    onChange(updated);
  }, [onChange, paper]);
  return { toggleStar, setReadStatus, addTag };
}
