"use client";

import { useEffect, useRef, useState } from "react";
import { search, type Item } from "@/lib/api";
import { CategoryTag, Poster } from "./Poster";

const MAX = 10;

/** Search bar with poster results, and a shelf of what the user picked.
 * Results: click, or arrow keys + Enter. Backspace in an empty search removes the last pick. */
export function LovedPicker({
  items,
  onChange,
  action,
}: {
  items: Item[];
  onChange: (items: Item[]) => void;
  /** the "What's next?" button, shown next to the shelf */
  action: React.ReactNode;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Item[]>([]);
  const [active, setActive] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResults([]);
      return;
    }
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      search(q.trim(), ctrl.signal, 16)
        .then((r) => {
          setResults(r.filter((x) => !items.some((i) => i.id === x.id)));
          setActive(0);
          setError(null);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError("Search isn't answering. Check that the WIN API is running.");
        });
    }, 200);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q, items]);

  function add(item: Item) {
    if (items.length >= MAX) return;
    onChange([...items, item]);
    setQ("");
    setResults([]);
    input.current?.focus();
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    // match the grid's column count (4 / 6 / 8, see the results list below)
    const cols = window.innerWidth >= 1024 ? 8 : window.innerWidth >= 640 ? 6 : 4;
    const move: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: cols, ArrowUp: -cols };
    if (e.key in move && results.length) {
      e.preventDefault();
      setActive((a) => Math.min(Math.max(a + move[e.key], 0), results.length - 1));
    } else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      add(results[active]);
    } else if (e.key === "Backspace" && !q && items.length) {
      onChange(items.slice(0, -1));
    } else if (e.key === "Escape") {
      setQ("");
    }
  }

  const searching = q.trim().length >= 2;

  return (
    <div className="flex flex-col gap-6">
      <label className="flex items-center gap-3 rounded-2xl border border-line bg-surface/90 px-5 py-4 backdrop-blur focus-within:border-accent">
        <svg viewBox="0 0 24 24" aria-hidden className="size-6 shrink-0 text-muted" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <input
          id="item-search"
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          disabled={items.length >= MAX}
          placeholder={items.length >= MAX ? "That's plenty: ask what's next" : "Search any title…"}
          aria-label="Search for something you loved"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls="search-results"
          aria-activedescendant={results[active] ? `result-${results[active].id}` : undefined}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent text-lg outline-none placeholder:text-muted focus-visible:outline-none"
        />
        {q && (
          <button type="button" onClick={() => setQ("")} aria-label="Clear search" className="text-muted hover:text-fg">
            ×
          </button>
        )}
      </label>

      {error && <p className="text-sm text-danger">{error}</p>}

      {searching && (
        <div className="rounded-2xl bg-surface/95 p-4 backdrop-blur">
          {results.length === 0 ? (
            <p className="text-sm text-muted">Nothing found for “{q.trim()}”. Try the original title or fewer words.</p>
          ) : (
            <ul
              id="search-results"
              role="listbox"
              aria-label="Search results"
              className="grid grid-cols-4 gap-3 sm:grid-cols-6 lg:grid-cols-8"
            >
              {results.map((r, i) => (
                <li
                  key={r.id}
                  id={`result-${r.id}`}
                  role="option"
                  aria-selected={i === active}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => {
                    e.preventDefault(); // keep focus in the search box
                    add(r);
                  }}
                  className="group flex cursor-pointer flex-col gap-1.5"
                >
                  <span className={`relative block rounded-lg ${i === active ? "ring-2 ring-accent ring-offset-2 ring-offset-surface" : ""}`}>
                    <Poster item={r} className="w-full" />
                    <span className="absolute right-1.5 top-1.5 grid size-7 place-items-center rounded-full bg-accent font-bold text-accent-ink opacity-0 shadow group-hover:opacity-100 group-aria-selected:opacity-100">
                      +
                    </span>
                  </span>
                  <span className="line-clamp-2 text-xs font-medium leading-snug sm:text-sm">{r.title}</span>
                  <span className="flex items-center gap-2 text-xs text-muted">
                    <CategoryTag item={r} />
                    {r.year && <span className="tabular-nums">{r.year}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex flex-col gap-3" role="group" aria-label="Your picks">
        <p className="text-sm text-muted">
          {items.length === 0
            ? "Your picks: add 2 to 5 things you loved for the best results."
            : `Your picks (${items.length})`}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          {items.map((it) => (
            <div key={it.id} className="group relative w-20 sm:w-24" title={it.title}>
              <Poster item={it} className="w-full" />
              <span className="mt-1 block truncate text-xs">{it.title}</span>
              <button
                type="button"
                aria-label={`Remove ${it.title}`}
                onClick={() => onChange(items.filter((x) => x.id !== it.id))}
                className="absolute -right-2 -top-2 grid size-7 place-items-center rounded-full bg-fg text-sm font-bold text-bg shadow"
              >
                ×
              </button>
            </div>
          ))}
          {items.length < MAX && (
            <button
              type="button"
              onClick={() => input.current?.focus()}
              aria-label="Add another"
              className="grid aspect-[2/3] w-20 place-items-center rounded-lg border-2 border-dashed border-line text-2xl text-muted hover:border-accent hover:text-accent sm:w-24"
            >
              +
            </button>
          )}
          <div className="self-center sm:ml-4">{action}</div>
        </div>
      </div>
    </div>
  );
}
