import { ImageResponse } from "next/og";

// Taste card (WIN-36): the preview image shown when a blend link is shared in a chat or post.
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "A WIN taste card: top genres and favourite titles";

// Built on the server: inside Docker the API is reached by its service name, not localhost.
const API = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// same palette as the app (dark theme values)
const COLOR: Record<string, string> = {
  movie: "#ef4444",
  tv: "#f2b43c",
  book: "#6aa8ff",
  game: "#b18cff",
  anime: "#ff7ab3",
};

type Shared = {
  liked: { title: string; category: string }[];
  top_genres: [string, number][];
};

export default async function Image({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  let data: Shared = { liked: [], top_genres: [] };
  try {
    const res = await fetch(`${API}/share/${encodeURIComponent(code)}`, { cache: "no-store" });
    if (res.ok) data = await res.json();
  } catch {
    /* API down: still return a valid card */
  }
  const max = Math.max(1, ...data.top_genres.map(([, n]) => n));

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          padding: "56px 64px",
          background: "#0a0a0a",
          color: "#fafafa",
          fontSize: 28,
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", fontSize: 56, fontWeight: 800 }}>
          WIN
          <span style={{ marginLeft: 18, fontSize: 28, color: "#a3a3a3", fontWeight: 400 }}>
            what is next
          </span>
        </div>

        <div style={{ display: "flex", flex: 1, marginTop: 44, gap: 64 }}>
          <div style={{ display: "flex", flexDirection: "column", width: 520, gap: 18 }}>
            {data.top_genres.length === 0 && <div style={{ color: "#a3a3a3" }}>No taste yet</div>}
            {data.top_genres.map(([genre, n]) => (
              <div key={genre} style={{ display: "flex", alignItems: "center", gap: 18 }}>
                <div style={{ width: 170, color: "#a3a3a3", fontSize: 24 }}>{genre}</div>
                <div
                  style={{
                    height: 26,
                    width: Math.round((300 * n) / max),
                    borderRadius: 6,
                    background: "#ff5a1f",
                  }}
                />
              </div>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", flex: 1, gap: 14 }}>
            <div style={{ color: "#a3a3a3", fontSize: 24 }}>I loved</div>
            {data.liked.slice(0, 6).map((item) => (
              <div key={item.title} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div
                  style={{
                    width: 14,
                    height: 14,
                    borderRadius: 3,
                    background: COLOR[item.category] ?? "#a3a3a3",
                  }}
                />
                <div style={{ fontSize: 28 }}>
                  {item.title.length > 32 ? item.title.slice(0, 31) + "…" : item.title}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", color: "#a3a3a3", fontSize: 24 }}>
          Open the link to blend our tastes and find something we both enjoy.
        </div>
      </div>
    ),
    size,
  );
}
