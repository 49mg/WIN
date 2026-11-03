"use client";

import { useCallback, useEffect, useState } from "react";
import type { Item, Recommendation } from "./api";

/** State kept in this browser until accounts exist (WIN-25). */
export type Feedback = Record<number, { liked: boolean; item: Recommendation }>;
export type QueueEntry = { item: Recommendation; done: boolean };

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(initial);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setValue(read(key, initial));
    setLoaded(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const update = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const v = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        try {
          localStorage.setItem(key, JSON.stringify(v));
        } catch {
          /* storage full or blocked: keep it in memory */
        }
        return v;
      });
    },
    [key],
  );

  return [value, update, loaded] as const;
}

export const useLiked = () => useStored<Item[]>("win.liked", []);
export const useFeedback = () => useStored<Feedback>("win.feedback", {});
export const useQueue = () => useStored<QueueEntry[]>("win.queue", []);
