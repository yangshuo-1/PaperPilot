import { useEffect, useState } from "react";
import { api, type ReadingBlock, type StructuredReading, type TranslationBlocks } from "../api";
import type { ReadingTranslationJob } from "../api/reading";

export function useParallelReading(paperId: string) {
  const [reading, setReading] = useState<StructuredReading | null>(null);
  const [translation, setTranslation] = useState<TranslationBlocks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState<ReadingTranslationJob | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all([api.getStructuredReading(paperId), api.getTranslationBlocks(paperId), api.getLatestReadingTranslationJob(paperId).catch(() => null)]).then(([source, translated, latestJob]) => {
      if (!alive) return;
      setReading(source);
      setTranslation(translated);
      setJob(latestJob);
      setLoading(false);
    }).catch((reason) => {
      if (!alive) return;
      setLoading(false);
      setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { alive = false; };
  }, [paperId]);

  useEffect(() => {
    if (!paperId || !job || !["queued", "running"].includes(job.status)) return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getReadingTranslationJob(paperId, job.job_id);
        setJob(next);
        if (next.status === "succeeded") {
          setTranslation(await api.getTranslationBlocks(paperId));
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : String(reason));
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [paperId, job?.job_id, job?.status]);

  async function generateTranslation(maxUnits = 40) {
    setError(null);
    try { setJob(await api.generateReadingTranslation(paperId, maxUnits)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  async function cancelTranslation() {
    if (!job) return;
    try { setJob(await api.cancelReadingTranslationJob(paperId, job.job_id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
  }

  const sourceBlocks = reading?.blocks || [];
  const translatedBlocks = translation?.blocks || translation?.chunks || [];
  const translatedById = new Map(translatedBlocks.map((block) => [block.block_id, block]));
  const blocks: ReadingBlock[] = sourceBlocks.map((block) => translatedById.get(block.block_id) ? { ...block, ...translatedById.get(block.block_id) } : block);
  return { reading, translation, blocks, loading, error, job, generateTranslation, cancelTranslation };
}
