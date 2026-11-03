import type { Item } from "@/lib/api";

/** Cover image, or the title's initials on the category color when there is no image. */
export function Poster({ item, className = "h-24 w-16" }: { item: Item; className?: string }) {
  const color = `var(--${item.category})`;
  if (item.image_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- covers come from 4 different CDNs
      <img
        src={item.image_url}
        alt=""
        loading="lazy"
        className={`${className} shrink-0 rounded-md bg-sunk object-cover`}
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
      className={`${className} grid shrink-0 place-items-center rounded-md font-display text-lg font-extrabold text-white`}
      style={{ background: color }}
    >
      {initials}
    </div>
  );
}

export function CategoryTag({ item }: { item: Item }) {
  return (
    <span
      className="text-[11px] font-semibold uppercase tracking-wider"
      style={{ color: `var(--${item.category})` }}
    >
      {item.category === "tv" ? "TV" : item.category}
    </span>
  );
}
