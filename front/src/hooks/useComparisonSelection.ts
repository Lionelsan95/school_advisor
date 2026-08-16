import { useCallback, useEffect, useState } from "react";

/**
 * Which establishments the reader has picked to place side by side.
 *
 * Held in memory for the session, not in `localStorage`. A comparison
 * selection is transient interface state, and persisting it would mean a
 * reader returning days later finds two establishments already paired up by a
 * past intention they no longer remember — which quietly suggests a shortlist
 * the product never meant to keep.
 *
 * Capped at two, matching `MAX_COMPARED` on the backend (docs/01 F4 and
 * docs/13 §9, whose A/B mobile layout assumes exactly two).
 */
export const MAX_SELECTED = 2;

const listeners = new Set<(uais: string[]) => void>();
let selection: string[] = [];

function publish() {
  for (const listener of listeners) listener([...selection]);
}

export function useComparisonSelection() {
  const [uais, setUais] = useState<string[]>(() => [...selection]);

  useEffect(() => {
    listeners.add(setUais);
    return () => {
      listeners.delete(setUais);
    };
  }, []);

  const toggle = useCallback((uai: string) => {
    if (selection.includes(uai)) {
      selection = selection.filter((item) => item !== uai);
    } else if (selection.length < MAX_SELECTED) {
      selection = [...selection, uai];
    } else {
      // Silently dropping the click would look broken; replacing the oldest
      // keeps the control responsive without ever exceeding two.
      selection = [...selection.slice(1), uai];
    }
    publish();
  }, []);

  const clear = useCallback(() => {
    selection = [];
    publish();
  }, []);

  return {
    uais,
    toggle,
    clear,
    isSelected: (uai: string) => uais.includes(uai),
    isReady: uais.length === MAX_SELECTED,
  };
}
