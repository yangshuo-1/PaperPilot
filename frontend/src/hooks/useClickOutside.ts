import { useEffect, useRef } from "react";

export function useClickOutside(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    function handlePointer(event: MouseEvent | TouchEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) closeRef.current();
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") closeRef.current();
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("touchstart", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("touchstart", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);
  return ref;
}
