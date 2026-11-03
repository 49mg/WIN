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
};

export const CATEGORY_LABEL: Record<Category, string> = {
  movie: "Movie",
  tv: "TV",
  book: "Book",
  game: "Game",
  anime: "Anime",
};

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`WIN API ${res.status}: ${await res.text()}`);
  return res.json();
}

/** Categories that actually have items in the database, e.g. ["anime", "book"]. */
export async function availableCategories(): Promise<Category[]> {
  const h = await call<{ items: Record<string, { total: number }> }>("/health");
  return (Object.keys(CATEGORY_LABEL) as Category[]).filter((c) => h.items[c]?.total > 0);
}

export function search(q: string, signal?: AbortSignal) {
  return call<Item[]>(`/search?q=${encodeURIComponent(q)}`, { signal });
}

export function recommend(body: {
  liked: number[];
  disliked?: number[];
  categories?: Category[];
  k?: number;
}) {
  return call<Recommendation[]>("/recommend", { method: "POST", body: JSON.stringify(body) });
}
