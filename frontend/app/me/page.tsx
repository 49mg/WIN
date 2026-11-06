"use client";

import Link from "next/link";
import { useState } from "react";
import { CategoryTag, Poster } from "@/components/Poster";
import { TasteRadar } from "@/components/TasteRadar";
import { userApi } from "@/lib/api";
import { useUser } from "@/lib/user";

export default function Me() {
  const { liked, feedback, queue, setDone, removeFromQueue, loaded, error, userId } = useUser();
  const [card, setCard] = useState<{ link: string; image: string } | null>(null);

  async function shareTaste() {
    if (!userId) return;
    const { code } = await userApi.share(userId);
    // cache-buster so the preview shows your latest taste, not an old image
    setCard({ link: `${window.location.origin}/blend/${code}`, image: `/blend/${code}/opengraph-image?v=${Date.now()}` });
  }

  const genres = [
    ...liked.flatMap((i) => i.genres ?? []),
    ...Object.values(feedback)
      .filter((f) => f.liked)
      .flatMap((f) => f.item.genres),
  ];
  const todo = queue.filter((q) => !q.done);
  const done = queue.filter((q) => q.done);

  function toggle(id: number) {
    setDone(id, !queue.find((e) => e.item.id === id)?.done);
  }
  function remove(id: number) {
    removeFromQueue(id);
  }

  const topGenres = [...genres.reduce((m, g) => m.set(g, (m.get(g) ?? 0) + 1), new Map<string, number>())]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([g]) => g);

  return (
    <div className="grid gap-12 pb-8 pt-6 sm:pt-12 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16">
      <section className="flex flex-col gap-5">
        <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
          Your taste
        </h1>
        <p className="max-w-[45ch] text-muted">
          {topGenres.length
            ? `Mostly ${topGenres.slice(0, -1).join(", ")}${topGenres.length > 1 ? " and " : ""}${topGenres.at(-1)}. `
            : ""}
          Built from the {liked.length} {liked.length === 1 ? "thing" : "things"} you loved and the
          picks you gave a thumbs up.
        </p>
        {error && <p className="text-sm text-danger">{error}</p>}
        {loaded && <TasteRadar genres={genres} />}
        {liked.length > 0 && (
          <ul className="flex flex-wrap gap-2" aria-label="Things you loved">
            {liked.map((it) => (
              <li key={it.id} className="inline-flex items-center gap-2 rounded-full bg-surface py-1 pl-1 pr-3 text-sm">
                <Poster item={it} className="w-6 rounded-full" />
                {it.title}
              </li>
            ))}
          </ul>
        )}
        {loaded && liked.length > 0 && !card && (
          <button
            type="button"
            onClick={() => shareTaste().catch(() => {})}
            className="self-start rounded-lg border border-line-strong px-4 py-2 text-sm font-medium hover:border-muted"
          >
            Share my taste
          </button>
        )}
        {card && (
          <div className="flex flex-col gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element -- generated on the server */}
            <img src={card.image} alt="Your taste card" width={600} height={315} className="max-w-full rounded-xl" />
            <p className="text-sm text-muted">
              Send this link: the card shows up as its preview, and friends who open it can blend
              their taste with yours.
            </p>
            <input
              id="share-link"
              readOnly
              value={card.link}
              onFocus={(e) => e.target.select()}
              className="rounded-lg border border-line-strong bg-surface px-4 py-2 text-sm"
            />
          </div>
        )}
      </section>

      <section className="flex flex-col gap-5">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="font-display text-3xl font-bold tracking-tight">Next queue</h2>
          {queue.length > 0 && (
            <span className="text-sm tabular-nums text-muted">
              {todo.length} to try · {done.length} done
            </span>
          )}
        </div>
        {loaded && queue.length === 0 && (
          <p className="rounded-xl border border-line bg-surface p-6 text-muted">
            Nothing saved yet. On{" "}
            <Link href="/" className="text-accent underline underline-offset-2">
              Discover
            </Link>
            , press Next queue on a pick you want to try.
          </p>
        )}
        <ul className="flex flex-col gap-2">
          {[...todo, ...done].map(({ item, done: isDone }) => (
            <li
              key={item.id}
              className={`flex items-center gap-4 rounded-xl border border-line bg-surface p-3 pr-4 ${isDone ? "opacity-60" : ""}`}
            >
              <Poster item={item} className="w-12" />
              <label htmlFor={`q-${item.id}`} className="flex min-w-0 flex-1 cursor-pointer flex-col gap-1">
                <span className={`truncate font-display text-lg font-bold ${isDone ? "line-through" : ""}`}>
                  {item.title}
                </span>
                <CategoryTag item={item} />
              </label>
              <span className="flex items-center gap-2 text-sm text-muted">
                <input
                  id={`q-${item.id}`}
                  type="checkbox"
                  checked={isDone}
                  onChange={() => toggle(item.id)}
                  className="size-5 accent-[var(--ok)]"
                />
                <span className="hidden sm:inline">Done</span>
              </span>
              <button
                type="button"
                onClick={() => remove(item.id)}
                className="grid size-8 place-items-center rounded-full text-muted hover:bg-sunk hover:text-fg"
                aria-label={`Remove ${item.title} from queue`}
                title="Remove from queue"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
