import { useEffect, useState } from "react";
import { getQuickview, type Quickview } from "../api";

export function useQuickview(paperId: string) {
  const [data, setData] = useState<Quickview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let alive = true;
    setLoaded(false); setError(null);
    getQuickview(paperId).then((value) => { if (alive) { setData(value); setLoaded(true); } }).catch((reason) => { if (alive) { setError(reason instanceof Error ? reason.message : String(reason)); setLoaded(true); } });
    return () => { alive = false; };
  }, [paperId]);
  return { data, error, loaded };
}
