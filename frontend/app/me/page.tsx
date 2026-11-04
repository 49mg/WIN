"use client";

import Link from "next/link";
import { CategoryTag, Poster } from "@/components/Poster";
import { TasteRadar } from "@/components/TasteRadar";
import { useUser } from "@/lib/user";

export default function Me() {
  const { liked, feedback, queue, setDone, removeFromQueue, loaded, error } = useUser();

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

  return (
    <div className="flex flex-col gap-10 pb-8 pt-6">
      <section className="flex flex-col gap-2">
        <h1 className="font-display text-3xl font-extrabold tracking-tight">Your taste</h1>
        <p className="text-sm text-muted">
          Built from the {liked.length} things you added and the picks you gave 👍.
        </p>
        {error && <p className="text-sm text-[var(--movie)]">{error}</p>}
        {loaded && <TasteRadar genres={genres} />}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-display text-2xl font-bold">Next queue</h2>
        {loaded && queue.length === 0 && (
          <p className="text-sm text-muted">
            Nothing queued yet. On{" "}
            <Link href="/" className="text-accent underline">
              Discover
            </Link>
            , press “+ Next queue” on a pick you want to try.
          </p>
        )}
        <ul className="flex flex-col divide-y divide-line rounded-2xl border border-line bg-surface">
          {[...todo, ...done].map(({ item, done: isDone }) => (
            <li key={item.id} className="flex items-center gap-3 px-4 py-3">
              <input
                id={`q-${item.id}`}
                type="checkbox"
                checked={isDone}
                onChange={() => toggle(item.id)}
                className="size-4 accent-[var(--ok)]"
              />
              <Poster item={item} className="h-12 w-8" />
              <label htmlFor={`q-${item.id}`} className="min-w-0 flex-1 cursor-pointer">
                <span className={`block truncate ${isDone ? "text-muted line-through" : ""}`}>
                  {item.title}
                </span>
                <CategoryTag item={item} />
              </label>
              <button
                type="button"
                onClick={() => remove(item.id)}
                className="text-xs text-muted hover:text-fg"
                aria-label={`Remove ${item.title} from queue`}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
