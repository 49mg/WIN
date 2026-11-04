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
  if (!res.ok) throw new ApiError(res.status, `WIN API ${res.status}: ${await res.text()}`);
  return res.status === 204 ? (undefined as T) : res.json();
}

// ---- the user's own data (anonymous account, id kept in this browser) ----

export type UserData = {
  id: string;
  liked: Item[];
  feedback: { item: Item; liked: boolean }[];
  queue: { item: Item; done: boolean }[];
};

const asUser = (userId: string, init: RequestInit = {}): RequestInit => ({
  ...init,
  headers: { "X-User-Id": userId },
});

export const userApi = {
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

export function search(q: string, signal?: AbortSignal) {
  return call<Item[]>(`/search?q=${encodeURIComponent(q)}`, { signal });
}

export function recommendVibe(body: {
  text: string;
  disliked?: number[];
  categories?: Category[];
  k?: number;
  use_llm?: boolean;
}) {
  return call<Recommendation[]>("/recommend/vibe", { method: "POST", body: JSON.stringify(body) });
}

export function recommend(body: {
  liked: number[];
  disliked?: number[];
  categories?: Category[];
  k?: number;
  use_llm?: boolean;
}) {
  return call<Recommendation[]>("/recommend", { method: "POST", body: JSON.stringify(body) });
}
