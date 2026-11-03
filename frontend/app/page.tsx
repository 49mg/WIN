"use client";

import { useEffect, useMemo, useState } from "react";
import { ItemSearch } from "@/components/ItemSearch";
import { RecCard } from "@/components/RecCard";
import {
  availableCategories,
  CATEGORY_LABEL,
  recommend,
  type Category,
  type Recommendation,
} from "@/lib/api";
import { useFeedback, useLiked, useQueue } from "@/lib/store";

export default function Discover() {
  const [liked, setLiked] = useLiked();
  const [feedback, setFeedback] = useFeedback();
  const [queue, setQueue] = useQueue();
  const [categories, setCategories] = useState<Category[]>([]);
  const [filter, setFilter] = useState<Category | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    availableCategories().then(setCategories).catch(() => setCategories([]));
  }, []);

  const votes = useMemo(() => {
    const up = Object.values(feedback).filter((f) => f.liked).map((f) => f.item.id);
    const down = Object.values(feedback).filter((f) => !f.liked).map((f) => f.item.id);
    return { up, down };
  }, [feedback]);

  async function run(nextFilter = filter) {
    if (!liked.length) return;
    setLoading(true);
    setError(null);
    try {
      const likedIds = [...new Set([...liked.map((i) => i.id), ...votes.up])];
      setRecs(
        await recommend({
          liked: likedIds,
          disliked: votes.down,
          categories: nextFilter ? [nextFilter] : [],
        }),
      );
      setStale(false);
    } catch {
      setError("Could not reach the WIN API. Start it with `docker compose up` and try again.");
    } finally {
      setLoading(false);
    }
  }

  function vote(rec: Recommendation, up: boolean) {
    setFeedback((f) => {
      const next = { ...f };
      if (next[rec.id]?.liked === up) delete next[rec.id];
      else next[rec.id] = { liked: up, item: rec };
      return next;
    });
    setStale(true);
  }

  function pickFilter(c: Category | null) {
    setFilter(c);
    if (recs) run(c);
  }

  const queuedIds = new Set(queue.map((q) => q.item.id));

  return (
    <div className="flex flex-col gap-8 pb-8">
      <section className="flex flex-col gap-4 pt-6">
        <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          What did you love?
        </h1>
        <p className="max-w-prose text-muted">
          Add a few things you enjoyed, from any category. WIN finds what to watch, read or play
          next, and tells you why.
        </p>
        <ItemSearch items={liked} onChange={setLiked} />
        <button
          type="button"
          disabled={!liked.length || loading}
          onClick={() => run()}
          className="rounded-xl bg-accent py-3 font-display text-lg font-bold text-accent-ink transition-opacity disabled:opacity-40"
        >
          {loading ? "Finding picks…" : "What's next? →"}
        </button>
        {error && <p className="text-sm text-[var(--movie)]">{error}</p>}
      </section>

      {recs && (
        <section className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter by category">
              {[null, ...categories].map((c) => (
                <button
                  key={c ?? "all"}
                  type="button"
                  role="tab"
                  aria-selected={filter === c}
                  onClick={() => pickFilter(c)}
                  className={`rounded-full border px-3 py-1 text-xs ${
                    filter === c ? "border-fg font-semibold" : "border-line text-muted"
                  }`}
                >
                  {c ? CATEGORY_LABEL[c] : "All"}
                </button>
              ))}
            </div>
            {stale && (
              <button
                type="button"
                onClick={() => run()}
                className="text-sm font-semibold text-accent underline-offset-4 hover:underline"
              >
                ↻ Update picks with your feedback
              </button>
            )}
          </div>

          <div className="rounded-2xl border border-line bg-surface px-4">
            {recs.length === 0 ? (
              <p className="py-10 text-center text-muted">
                No picks here yet. Try another category or add more things you loved.
              </p>
            ) : (
              recs.map((r) => (
                <RecCard
                  key={r.id}
                  rec={r}
                  feedback={feedback[r.id]?.liked}
                  queued={queuedIds.has(r.id)}
                  onFeedback={(up) => vote(r, up)}
                  onQueue={() => setQueue((q) => [...q, { item: r, done: false }])}
                />
              ))
            )}
          </div>
        </section>
      )}
    </div>
  );
}
