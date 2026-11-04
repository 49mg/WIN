"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { ApiError, userApi, type Item, type UserData } from "./api";

const ID_KEY = "win.userId";
const OLD_KEYS = ["win.liked", "win.feedback", "win.queue"]; // browser-only storage before WIN-25

export type Feedback = Record<number, { liked: boolean; item: Item }>;
export type QueueEntry = { item: Item; done: boolean };

type UserState = {
  loaded: boolean;
  error: string | null;
  userId: string | null;
  liked: Item[];
  feedback: Feedback;
  queue: QueueEntry[];
  setLiked: (items: Item[]) => void;
  /** up = true/false sets a vote; the same vote again removes it */
  vote: (item: Item, up: boolean) => void;
  addToQueue: (item: Item) => void;
  setDone: (itemId: number, done: boolean) => void;
  removeFromQueue: (itemId: number) => void;
};

const UserContext = createContext<UserState | null>(null);

export function useUser(): UserState {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used inside <UserProvider>");
  return ctx;
}

function readLocal(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null; // storage blocked: the user simply gets a fresh account each visit
  }
}

function writeLocal(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

/** One-time upload of what an earlier version kept only in this browser. */
async function migrateOldData(userId: string) {
  const parse = <T,>(key: string): T | null => {
    try {
      return JSON.parse(readLocal(key) ?? "null") as T | null;
    } catch {
      return null;
    }
  };
  const liked = parse<Item[]>("win.liked");
  const feedback = parse<Feedback>("win.feedback");
  const queue = parse<QueueEntry[]>("win.queue");
  if (liked?.length) await userApi.setLiked(userId, liked.map((i) => i.id));
  for (const f of Object.values(feedback ?? {})) await userApi.vote(userId, f.item.id, f.liked);
  for (const q of queue ?? []) {
    await userApi.queueAdd(userId, q.item.id);
    if (q.done) await userApi.queueDone(userId, q.item.id, true);
  }
  OLD_KEYS.forEach((k) => writeLocal(k, null));
}

function toState(d: UserData) {
  return {
    liked: d.liked,
    feedback: Object.fromEntries(d.feedback.map((f) => [f.item.id, f])) as Feedback,
    queue: d.queue,
  };
}

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [userId, setUserId] = useState<string | null>(null);
  const [data, setData] = useState<ReturnType<typeof toState>>({ liked: [], feedback: {}, queue: [] });
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const idRef = useRef<string | null>(null);
  const started = useRef(false); // React runs effects twice in development: create one user, not two
  // Saves wait for the account to exist, then run one at a time in the order they were made,
  // so quick changes (or changes made while the page is still loading) are never lost or reordered.
  const ready = useRef<{ promise: Promise<string>; resolve: (id: string) => void } | null>(null);
  if (!ready.current) {
    let resolve!: (id: string) => void;
    const promise = new Promise<string>((r) => (resolve = r));
    ready.current = { promise, resolve };
  }
  const chain = useRef<Promise<unknown>>(Promise.resolve());
  const changedWhileLoading = useRef(false);

  const refresh = useCallback(async () => {
    if (idRef.current) setData(toState(await userApi.me(idRef.current)));
  }, []);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    (async () => {
      try {
        let id = readLocal(ID_KEY);
        let me: UserData | null = null;
        if (id) {
          try {
            me = await userApi.me(id);
          } catch (e) {
            if (!(e instanceof ApiError && e.status === 401)) throw e;
            id = null; // the server doesn't know this id (e.g. database reset): start over
          }
        }
        if (!id || !me) {
          me = await userApi.create();
          id = me.id;
          writeLocal(ID_KEY, id);
          await migrateOldData(id);
          me = await userApi.me(id);
        }
        idRef.current = id;
        setUserId(id);
        // keep what the user already changed on screen; those saves run right after this
        if (!changedWhileLoading.current) setData(toState(me));
        ready.current!.resolve(id);
      } catch {
        setError("Could not load your saved picks. Is the WIN API running?");
      } finally {
        setLoaded(true);
      }
    })();
  }, []);

  /** Update the screen now, save in the background; if saving fails, reload the truth. */
  const save = useCallback(
    (optimistic: (d: ReturnType<typeof toState>) => ReturnType<typeof toState>, request: (id: string) => Promise<unknown>) => {
      setData(optimistic);
      if (!idRef.current) changedWhileLoading.current = true;
      chain.current = chain.current
        .then(() => ready.current!.promise)
        .then((id) => request(id))
        .then(() => setError(null))
        .catch(() => {
          setError("A change could not be saved. Your list was reloaded.");
          return refresh().catch(() => {});
        });
    },
    [refresh],
  );

  const value: UserState = {
    loaded,
    error,
    userId,
    ...data,
    setLiked: (items) =>
      save((d) => ({ ...d, liked: items }), (id) => userApi.setLiked(id, items.map((i) => i.id))),
    vote: (item, up) => {
      const removing = data.feedback[item.id]?.liked === up;
      save(
        (d) => {
          const feedback = { ...d.feedback };
          if (removing) delete feedback[item.id];
          else feedback[item.id] = { liked: up, item };
          return { ...d, feedback };
        },
        (id) => (removing ? userApi.unvote(id, item.id) : userApi.vote(id, item.id, up)),
      );
    },
    addToQueue: (item) =>
      save(
        (d) => (d.queue.some((q) => q.item.id === item.id) ? d : { ...d, queue: [...d.queue, { item, done: false }] }),
        (id) => userApi.queueAdd(id, item.id),
      ),
    setDone: (itemId, done) =>
      save(
        (d) => ({ ...d, queue: d.queue.map((q) => (q.item.id === itemId ? { ...q, done } : q)) }),
        (id) => userApi.queueDone(id, itemId, done),
      ),
    removeFromQueue: (itemId) =>
      save(
        (d) => ({ ...d, queue: d.queue.filter((q) => q.item.id !== itemId) }),
        (id) => userApi.queueRemove(id, itemId),
      ),
  };

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}
