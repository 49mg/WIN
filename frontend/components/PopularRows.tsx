"use client";

import { CATEGORY_LABEL, type Category, type Item } from "@/lib/api";
import { Poster } from "./Poster";

const ORDER: Category[] = ["movie", "tv", "game", "anime", "book"];
const HEADING: Record<Category, string> = {
  movie: "Popular movies",
  tv: "Popular TV shows",
  game: "Popular games",
  anime: "Popular anime",
  book: "Popular books",
};

/** Before the first search: popular titles per category. Clicking one adds it to "I loved". */
export function PopularRows({
  popular,
  likedIds,
  onAdd,
}: {
  popular: Partial<Record<Category, Item[]>>;
  likedIds: Set<number>;
  onAdd: (item: Item) => void;
}) {
  const rows = ORDER.filter((c) => popular[c]?.length);
  if (!rows.length) return null;
  return (
    <section className="relative flex flex-col gap-10" aria-label="Popular titles">
      <p className="max-w-[60ch] text-muted">
        Not sure where to start? Tap anything you loved below to add it to your picks.
      </p>
      {rows.map((c) => (
        <div key={c} className="flex flex-col gap-4">
          <h2 className="flex items-center gap-2 font-display text-2xl font-bold tracking-tight">
            <span className="size-2.5 rounded-full" style={{ background: `var(--${c})` }} />
            {HEADING[c]}
          </h2>
          <ul className="-mx-4 flex gap-4 overflow-x-auto px-4 pb-2 sm:-mx-6 sm:px-6" aria-label={HEADING[c]}>
            {popular[c]!.map((it) => {
              const added = likedIds.has(it.id);
              return (
                <li key={it.id} className="w-32 shrink-0 sm:w-36">
                  <button
                    type="button"
                    onClick={() => onAdd(it)}
                    disabled={added}
                    aria-label={added ? `${it.title} is in what you loved` : `Add ${it.title} to what you loved`}
                    className="group flex w-full flex-col gap-2 text-left"
                  >
                    <span className="relative block">
                      <Poster item={it} className="w-full transition-transform group-hover:-translate-y-1 group-disabled:opacity-40" />
                      <span
                        className={`absolute right-2 top-2 grid size-8 place-items-center rounded-full text-lg font-bold shadow-lg ${
                          added ? "bg-ok text-bg" : "bg-bg/80 text-fg opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100"
                        }`}
                      >
                        {added ? "✓" : "+"}
                      </span>
                    </span>
                    <span className="line-clamp-2 text-sm font-medium leading-snug">{it.title}</span>
                    <span className="text-xs text-muted">
                      {CATEGORY_LABEL[it.category]}
                      {it.year ? ` · ${it.year}` : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </section>
  );
}
