"use client";

import { useEffect, useRef, useState } from "react";
import { search, type Item } from "@/lib/api";

/** Chip input: type a title, pick from suggestions across all categories. */
export function ItemSearch({
  items,
  onChange,
}: {
  items: Item[];
  onChange: (items: Item[]) => void;
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
      search(q.trim(), ctrl.signal)
        .then((r) => {
          setResults(r.filter((x) => !items.some((i) => i.id === x.id)));
          setActive(0);
          setError(null);
        })
        .catch((e) => {
          if (e.name !== "AbortError") setError("Search is not reachable. Is the API running?");
        });
    }, 200);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [q, items]);

  function add(item: Item) {
    onChange([...items, item]);
    setQ("");
    setResults([]);
    input.current?.focus();
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") setActive((a) => Math.min(a + 1, results.length - 1));
    else if (e.key === "ArrowUp") setActive((a) => Math.max(a - 1, 0));
    else if (e.key === "Enter" && results[active]) {
      e.preventDefault();
      add(results[active]);
    } else if (e.key === "Backspace" && !q && items.length) onChange(items.slice(0, -1));
    else if (e.key === "Escape") setResults([]);
    else return;
    if (e.key !== "Enter" && e.key !== "Backspace") e.preventDefault();
  }

  return (
    <div className="relative">
      <div
        className="flex min-h-14 flex-wrap items-center gap-2 rounded-xl border-[1.5px] border-line bg-surface p-2.5 focus-within:border-accent"
        onClick={() => input.current?.focus()}
      >
        {items.map((it) => (
          <span
            key={it.id}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-bg py-1 pl-2 pr-1 text-sm"
          >
            <span className="size-2 rounded-sm" style={{ background: `var(--${it.category})` }} />
            {it.title}
            <button
              type="button"
              aria-label={`Remove ${it.title}`}
              className="rounded px-1 text-muted hover:bg-sunk hover:text-fg"
              onClick={() => onChange(items.filter((x) => x.id !== it.id))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          id="item-search"
          ref={input}
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          placeholder={items.length ? "Add more…" : "An anime, a book, a movie, a game…"}
          className="min-w-40 flex-1 bg-transparent px-1 py-1 outline-none placeholder:text-muted"
          role="combobox"
          aria-expanded={results.length > 0}
          aria-controls="search-results"
          autoComplete="off"
        />
      </div>

      {error && <p className="mt-2 text-sm text-[var(--movie)]">{error}</p>}

      {results.length > 0 && (
        <ul
          id="search-results"
          role="listbox"
          className="absolute z-10 mt-1 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-lg"
        >
          {results.map((r, i) => (
            <li
              key={r.id}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onMouseDown={(e) => {
                e.preventDefault();
                add(r);
              }}
              className={`flex cursor-pointer justify-between gap-3 px-3 py-2 text-sm ${i === active ? "bg-sunk" : ""}`}
            >
              <span className="truncate">{r.title}</span>
              <span className="shrink-0 text-xs text-muted">
                {r.category === "tv" ? "TV" : r.category}
                {r.year ? ` · ${r.year}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
