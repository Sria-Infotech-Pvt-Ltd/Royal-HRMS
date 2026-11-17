import { useCallback, useState } from "react";

/**
 * Which branches of an org chart are open. Starts with the first `openDepth` levels open; the user can flip any one branch, or open
 * or close all of them. A branch can also be forced open (a search match lies beneath it) without losing the user's own choices.
 */
export function useChartBranches(openDepth: number) {
  const [flipped, setFlipped] = useState<Set<string>>(new Set());
  const [everyBranch, setEveryBranch] = useState<boolean | null>(null);

  const isOpen = useCallback((id: string, depth: number, isForcedOpen = false): boolean => {
    if (isForcedOpen) return true;
    const byDefault = everyBranch ?? depth < openDepth;
    return flipped.has(id) ? !byDefault : byDefault;
  }, [flipped, everyBranch, openDepth]);

  const flip = useCallback((id: string) => {
    setFlipped(previous => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const setAll = useCallback((open: boolean) => { setEveryBranch(open); setFlipped(new Set()); }, []);

  return { isOpen, flip, setAll };
}
