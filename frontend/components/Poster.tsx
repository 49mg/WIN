"use client";

import { useState } from "react";
import { CATEGORY_LABEL, type Item } from "@/lib/api";

/** Cover image (2:3), or the title's initials on the category colour when there is none
 * or the image fails to load (some source links are broken). */
export function Poster({ item, className = "w-16" }: { item: Item; className?: string }) {
  const [broken, setBroken] = useState(false);
  const base = `${className} aspect-[2/3] shrink-0 overflow-hidden rounded-lg bg-sunk`;
  if (item.image_url && !broken) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- covers come from 4 different CDNs
      <img
        src={item.image_url}
        alt=""
        loading="lazy"
        onError={() => setBroken(true)}
        className={`${base} object-cover`}
      />
    );
  }
  const initials = item.title
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("");
  return (
    <div
      className={`${base} grid place-items-center font-display text-2xl font-extrabold text-white`}
      style={{ background: `var(--${item.category})` }}
    >
      {initials}
    </div>
  );
}

export function CategoryTag({ item }: { item: Item }) {
  return (
    <span data-category={item.category} className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span className="size-2 rounded-full" style={{ background: `var(--${item.category})` }} />
      {CATEGORY_LABEL[item.category] ?? item.category}
    </span>
  );
}
