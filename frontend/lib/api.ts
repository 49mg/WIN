export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Category = "movie" | "tv" | "book" | "game" | "anime";

export type Item = {
  id: number;
  title: string;
  category: Category;
  year: number | null;
  image_url: string | null;
  genres: string[];
};

export type Recommendation = Item & {
  description: string | null;
  creators: string[];
  match: number;
  reason: string;
  ai: boolean; // picked and explained by the LLM re-ranker
};

export const CATEGORY_LABEL: Record<Category, string> = {
  movie: "Movie",
  tv: "TV",
  book: "Book",
  game: "Game",
  anime: "Anime",
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    // FastAPI errors look like {"detail": "message"}; show that message when there is one
    const text = await res.text();
    let detail = text;
    try {
      const d = JSON.parse(text).detail;
      if (typeof d === "string") detail = d;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

// ---- the user's own data (anonymous account, id kept in this browser) ----

export type UserData = {
  id: string;
  arm: "llm" | "engine"; // A/B test group: with or without LLM re-ranking
  liked: Item[];
  feedback: { item: Item; liked: boolean }[];
  queue: { item: Item; done: boolean }[];
};

const asUser = (userId: string, init: RequestInit = {}): RequestInit => ({
  ...init,
  headers: { "X-User-Id": userId },
});

export type UsageEvent = {
  event: "impression" | "like" | "dislike" | "queue";
  item_id: number;
  list_id: string;
  mode: "titles" | "vibe";
  source: "engine" | "llm";
  position: number;
};

export const userApi = {
  share: (u: string) => call<{ code: string }>("/me/share", asUser(u, { method: "POST" })),
  blend: (u: string, code: string, k = 11) =>
    call<Recommendation[]>("/blend", asUser(u, { method: "POST", body: JSON.stringify({ code, k }) })),
  logEvents: (u: string, events: UsageEvent[]) =>
    call<void>("/me/events", asUser(u, { method: "POST", body: JSON.stringify({ events }) })),
  create: () => call<UserData>("/users", { method: "POST" }),
  me: (u: string) => call<UserData>("/me", asUser(u)),
  setLiked: (u: string, itemIds: number[]) =>
    call<UserData>("/me/liked", asUser(u, { method: "PUT", body: JSON.stringify({ item_ids: itemIds }) })),
  vote: (u: string, itemId: number, liked: boolean) =>
    call<void>(`/me/feedback/${itemId}`, asUser(u, { method: "PUT", body: JSON.stringify({ liked }) })),
  unvote: (u: string, itemId: number) =>
    call<void>(`/me/feedback/${itemId}`, asUser(u, { method: "DELETE" })),
  queueAdd: (u: string, itemId: number) =>
    call<void>("/me/queue", asUser(u, { method: "POST", body: JSON.stringify({ item_id: itemId }) })),
  queueDone: (u: string, itemId: number, done: boolean) =>
    call<void>(`/me/queue/${itemId}`, asUser(u, { method: "PATCH", body: JSON.stringify({ done }) })),
  queueRemove: (u: string, itemId: number) =>
    call<void>(`/me/queue/${itemId}`, asUser(u, { method: "DELETE" })),
};

/** Categories that actually have items in the database, e.g. ["anime", "book"]. */
export async function availableCategories(): Promise<Category[]> {
  const h = await call<{ items: Record<string, { total: number }> }>("/health");
  return (Object.keys(CATEGORY_LABEL) as Category[]).filter((c) => h.items[c]?.total > 0);
}

export function search(q: string, signal?: AbortSignal, limit = 8) {
  return call<Item[]>(`/search?q=${encodeURIComponent(q)}&limit=${limit}`, { signal });
}

// The user id lets the server check the A/B arm: only "llm" users get the paid AI step.
const userHeader = (userId?: string | null): HeadersInit => (userId ? { "X-User-Id": userId } : {});

export function recommendVibe(
  body: { text: string; disliked?: number[]; categories?: Category[]; k?: number; use_llm?: boolean },
  userId?: string | null,
) {
  return call<Recommendation[]>("/recommend/vibe", {
    method: "POST",
    body: JSON.stringify(body),
    headers: userHeader(userId),
  });
}

export function recommend(
  body: { liked: number[]; disliked?: number[]; categories?: Category[]; k?: number; use_llm?: boolean },
  userId?: string | null,
) {
  return call<Recommendation[]>("/recommend", {
    method: "POST",
    body: JSON.stringify(body),
    headers: userHeader(userId),
  });
}

// ---- online metrics (A/B test, WIN-37) ----

export type Rate = { value: number; low: number; high: number };
export type ArmStats = {
  arm: "llm" | "engine";
  mode: "titles" | "vibe";
  users: number;
  lists: number;
  impressions: number;
  like_rate: Rate;
  dislike_rate: Rate;
  queue_rate: Rate;
  positive_rate: Rate;
};
export type LlmDay = { day: string; calls: number; input_tokens: number; output_tokens: number; cost_usd: number };
export type Metrics = {
  users_per_arm: Record<string, number>;
  results: ArmStats[];
  llm: { daily_cap: number; calls_today: number; cost_today_usd: number; last_7_days: LlmDay[] };
  latency: { kind: string; count: number; p50_ms: number; p95_ms: number }[]; // since the API started
};

export const getMetrics = () => call<Metrics>("/metrics");

// ---- share codes (read-only view of what someone loved) ----

export type SharedTaste = { code: string; liked: Item[]; top_genres: [string, number][] };
export const getShared = (code: string) => call<SharedTaste>(`/share/${encodeURIComponent(code)}`);

/** Most popular items with a cover, per category (home page before a search). */
export const getPopular = (perCategory = 12) =>
  call<Partial<Record<Category, Item[]>>>(`/popular?per_category=${perCategory}`);
