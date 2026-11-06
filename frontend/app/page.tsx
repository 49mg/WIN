"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { LovedPicker } from "@/components/LovedPicker";
import { PopularRows } from "@/components/PopularRows";
import { PosterWall } from "@/components/PosterWall";
import { RecCard } from "@/components/RecCard";
import {
  ApiError,
  availableCategories,
  CATEGORY_LABEL,
  getPopular,
  recommend,
  recommendVibe,
  search,
  type Category,
  type Item,
  type Recommendation,
  type UsageEvent,
} from "@/lib/api";
import { useUser } from "@/lib/user";

type Mode = "titles" | "vibe";
// 1 featured pick + 10 posters: two full rows of five on desktop, five rows of two on phones
const K = 11;
const STARTERS = [
  ["Interstellar", "Dune"],
  ["Death Note", "Breaking Bad"],
  ["The Witcher 3: Wild Hunt", "Spirited Away"],
];
const VIBE_EXAMPLES = [
  "cozy and a bit sad, for a rainy night",
  "dark psychological mind games",
  "epic space adventure with politics",
];

export default function Discover() {
  const [mode, setMode] = useState<Mode>("titles");
  const [vibe, setVibe] = useState("");
  const {
    liked, setLiked, feedback, vote: saveVote, queue, addToQueue, error: saveError, arm, logEvents, userId,
  } = useUser();
  const [categories, setCategories] = useState<Category[]>([]);
  const [popular, setPopular] = useState<Partial<Record<Category, Item[]>>>({});
  const [filter, setFilter] = useState<Category | null>(null);
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refining, setRefining] = useState(false);
  const runId = useRef(0); // ignore answers from an older search
  const recsRef = useRef<Recommendation[] | null>(null);
  recsRef.current = recs;
  const pendingVote = useRef<{ position: number; timer?: ReturnType<typeof setTimeout> }>({
    position: Infinity,
  });
  // the list on screen, for online metrics: live-feedback refreshes continue the same list
  const list = useRef<{ id: string; mode: Mode; shown: Set<number> }>({
    id: "",
    mode: "titles",
    shown: new Set(),
  });

  const event = (e: UsageEvent["event"], r: Recommendation, position: number): UsageEvent => ({
    event: e,
    item_id: r.id,
    list_id: list.current.id,
    mode: list.current.mode,
    source: r.ai ? "llm" : "engine",
    position,
  });

  /** Log what the user actually sees once a list is final (each card once per list). */
  function logShown(cards: Recommendation[]) {
    const fresh = cards
      .map((r, i) => [r, i] as const)
      .filter(([r]) => !list.current.shown.has(r.id));
    fresh.forEach(([r]) => list.current.shown.add(r.id));
    logEvents(fresh.map(([r, i]) => event("impression", r, i)));
  }

  useEffect(() => {
    availableCategories().then(setCategories).catch(() => setCategories([]));
    getPopular(12).then(setPopular).catch(() => setPopular({}));
  }, []);

  const votes = useMemo(() => {
    const up = Object.values(feedback).filter((f) => f.liked).map((f) => f.item.id);
    const down = Object.values(feedback).filter((f) => !f.liked).map((f) => f.item.id);
    return { up, down };
  }, [feedback]);
  const votesRef = useRef(votes);
  votesRef.current = votes;

  const canRun = mode === "titles" ? liked.length > 0 : vibe.trim().length >= 3;

  /** Two steps: the engine's picks show at once (~0.2s), then the AI-refined list
   * replaces them when it arrives (a few seconds). If the AI step fails, the first list stays.
   * `keep`: cards that stay at the top (live feedback refreshes only the cards below a vote). */
  async function run(nextFilter = filter, keep: Recommendation[] = []) {
    if (!canRun) return;
    const id = ++runId.current;
    if (!keep.length) {
      setLoading(true);
      list.current = { id: crypto.randomUUID(), mode, shown: new Set() };
    }
    setRefining(false);
    setError(null);
    const cats = nextFilter ? [nextFilter] : [];
    const { up, down } = votesRef.current;
    const fetchPicks = (use_llm: boolean) =>
      mode === "vibe"
        ? recommendVibe({ text: vibe.trim(), disliked: down, categories: cats, use_llm, k: K }, userId)
        : recommend(
            {
              liked: [...new Set([...liked.map((i) => i.id), ...up])],
              disliked: down,
              categories: cats,
              use_llm,
              k: K,
            },
            userId,
          );
    const withKept = (fresh: Recommendation[]) => {
      const keptIds = new Set(keep.map((r) => r.id));
      return [...keep, ...fresh.filter((r) => !keptIds.has(r.id))].slice(0, K);
    };
    let shown: Recommendation[];
    try {
      const fast = await fetchPicks(false);
      if (id !== runId.current) return;
      shown = withKept(fast);
      setRecs(shown);
    } catch (e) {
      if (id === runId.current) {
        setError(
          e instanceof ApiError && e.status === 429
            ? e.message // "Too many requests. Try again in N seconds."
            : "Could not reach the WIN API. Start it with `docker compose up` and try again.",
        );
        setLoading(false);
      }
      return;
    }
    setLoading(false);
    if (arm === "engine") {
      logShown(shown); // A/B holdout: this user never gets the LLM step
      return;
    }
    setRefining(true);
    try {
      const refined = await fetchPicks(true);
      if (id === runId.current && refined.some((r) => r.ai)) {
        shown = withKept(refined);
        setRecs(shown);
      }
    } catch {
      /* keep the engine's picks */
    } finally {
      if (id === runId.current) {
        setRefining(false);
        logShown(shown);
      }
    }
  }

  /** Live feedback: 👎 hides the card at once; shortly after the last vote, the cards below
   * the highest voted card are replaced with picks that use the new votes. */
  function vote(rec: Recommendation, up: boolean, position: number) {
    const undo = feedback[rec.id]?.liked === up; // pressing the same vote again removes it
    saveVote(rec, up);
    if (undo) return;
    logEvents([event(up ? "like" : "dislike", rec, position)]);
    if (!up) setRecs((r) => r?.filter((x) => x.id !== rec.id) ?? r);
    const pending = pendingVote.current;
    pending.position = Math.min(pending.position, up ? position : position - 1);
    clearTimeout(pending.timer);
    pending.timer = setTimeout(() => {
      const keep = (recsRef.current ?? []).slice(0, pending.position + 1);
      pending.position = Infinity;
      run(filter, keep);
    }, 900);
  }

  function pickFilter(c: Category | null) {
    setFilter(c);
    if (recs) run(c);
  }

  const queuedIds = new Set(queue.map((q) => q.item.id));

  /** Empty state: fill the sentence with a ready-made set of titles. */
  async function applyStarter(titles: string[]) {
    const found = await Promise.all(
      titles.map((t) =>
        search(t)
          .then((r) => r.find((x) => x.title.toLowerCase() === t.toLowerCase()) ?? r[0])
          .catch(() => undefined),
      ),
    );
    const items = found.filter((x): x is Item => !!x);
    if (items.length) setLiked(items);
  }

  /** Popular rows: add a title to the sentence and bring the sentence into view. */
  function addFromPopular(item: Item) {
    if (liked.some((x) => x.id === item.id)) return;
    setLiked([...liked, item]);
    const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: smooth ? "smooth" : "auto" });
  }

  const nextButton = (
    <button
      type="button"
      disabled={!canRun || loading}
      onClick={() => run()}
      className="rounded-lg bg-fg px-7 py-3.5 font-display text-lg font-bold text-bg transition-opacity hover:opacity-90 disabled:opacity-35"
    >
      {loading ? "Finding picks…" : "What's next?"}
    </button>
  );

  const card = (r: Recommendation, i: number, variant: "featured" | "tile") => (
    <RecCard
      key={r.id}
      rec={r}
      variant={variant}
      feedback={feedback[r.id]?.liked}
      queued={queuedIds.has(r.id)}
      onFeedback={(up) => vote(r, up, i)}
      onQueue={() => {
        addToQueue(r);
        logEvents([event("queue", r, i)]);
      }}
    />
  );

  return (
    <div className="flex flex-col gap-14 pb-8">
      <section className="relative isolate flex flex-col gap-8 pt-6 sm:pt-12">
        <PosterWall items={Object.values(popular).flat()} />
        <div className="inline-flex self-start gap-1.5" role="tablist" aria-label="How to search">
          {(["titles", "vibe"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => {
                setMode(m);
                setRecs(null);
              }}
              className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
                mode === m ? "border-fg bg-fg font-medium text-bg" : "border-line-strong text-muted hover:text-fg"
              }`}
            >
              {m === "titles" ? "By titles" : "By vibe"}
            </button>
          ))}
        </div>

        <div className="flex max-w-3xl flex-col gap-3">
          <h1 className="font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-6xl">
            {mode === "titles" ? "What did you love?" : "What are you in the mood for?"}
          </h1>
          <p className="max-w-[60ch] text-lg text-muted">
            {mode === "titles"
              ? "Pick a few movies, shows, games, anime or books you enjoyed. WIN finds what to try next and tells you why."
              : "Describe a feeling, a setting or a kind of story in your own words."}
          </p>
        </div>

        {mode === "titles" ? (
          <LovedPicker items={liked} onChange={setLiked} action={nextButton} />
        ) : (
          <div className="flex flex-col gap-4">
            <label htmlFor="vibe-text" className="sr-only">
              Describe your mood
            </label>
            <textarea
              id="vibe-text"
              value={vibe}
              onChange={(e) => setVibe(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  run();
                }
              }}
              rows={2}
              maxLength={300}
              placeholder="something cozy and a bit sad, for a rainy night"
              className="resize-none rounded-xl border border-line-strong bg-surface/90 px-5 py-4 text-lg outline-none backdrop-blur placeholder:text-muted focus:border-accent focus-visible:outline-none"
            />
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              {nextButton}
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
                <span>Try</span>
                {VIBE_EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    type="button"
                    onClick={() => setVibe(ex)}
                    className="rounded-full border border-line-strong px-3 py-1.5 text-muted hover:text-fg"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {mode === "titles" && liked.length === 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>Or start with</span>
            {STARTERS.map((set) => (
              <button
                key={set.join("+")}
                type="button"
                onClick={() => applyStarter(set)}
                className="rounded-full border border-line-strong px-3 py-1.5 text-muted hover:text-fg"
              >
                {set.join(" + ")}
              </button>
            ))}
          </div>
        )}
        {(error || saveError) && <p className="text-sm text-danger">{error || saveError}</p>}
      </section>

      {!recs && mode === "titles" && (
        <PopularRows popular={popular} likedIds={new Set(liked.map((i) => i.id))} onAdd={addFromPopular} />
      )}

      {recs && (
        <section className="relative flex flex-col gap-6" aria-label="Your picks">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
            <div
              className="-mx-4 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0"
              role="tablist"
              aria-label="Filter by category"
            >
              {[null, ...categories].map((c) => (
                <button
                  key={c ?? "all"}
                  type="button"
                  role="tab"
                  aria-selected={filter === c}
                  onClick={() => pickFilter(c)}
                  className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition-colors ${
                    filter === c ? "border-fg bg-fg text-bg" : "border-line-strong text-muted hover:text-fg"
                  }`}
                >
                  {c && <span className="size-2 rounded-full" style={{ background: `var(--${c})` }} />}
                  {c ? CATEGORY_LABEL[c] : "All"}
                </button>
              ))}
            </div>
            {refining && (
              <span className="text-sm text-muted motion-safe:animate-pulse" role="status">
                ✦ Refining with AI…
              </span>
            )}
          </div>

          {recs.length === 0 ? (
            <p className="py-16 text-center text-muted">
              No picks here yet. Try another category, or add more things you loved.
            </p>
          ) : (
            <>
              {card(recs[0], 0, "featured")}
              <div className="grid grid-cols-2 gap-x-4 gap-y-10 sm:gap-x-5 md:grid-cols-5">
                {recs.slice(1).map((r, i) => card(r, i + 1, "tile"))}
              </div>
            </>
          )}
        </section>
      )}
    </div>
  );
}
