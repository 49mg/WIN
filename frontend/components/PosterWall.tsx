import type { Item } from "@/lib/api";

/** Decorative backdrop behind the hero: a tilted, dimmed mosaic of real covers from the
 * catalog that fades into the page, so the first screen shows what WIN is about. */
export function PosterWall({ items }: { items: Item[] }) {
  if (items.length < 12) return null;
  // spread categories through the wall instead of grouping them
  const mixed = [...items].sort((a, b) => ((a.id * 7919) % 101) - ((b.id * 7919) % 101)).slice(0, 48);
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute left-1/2 top-0 -z-10 h-[34rem] w-screen -translate-x-1/2 overflow-hidden sm:h-[40rem]"
      // fade the wall in at the top and out at the bottom: no hard edges
      style={{
        maskImage: "linear-gradient(to bottom, transparent, black 18%, black 55%, transparent)",
        WebkitMaskImage: "linear-gradient(to bottom, transparent, black 18%, black 55%, transparent)",
      }}
    >
      <div className="absolute -left-24 -right-24 -top-28 grid rotate-[-8deg] grid-cols-6 gap-3 opacity-45 sm:grid-cols-8 lg:grid-cols-12">
        {mixed.map((it) => (
          // eslint-disable-next-line @next/next/no-img-element -- decorative, covers from 4 CDNs
          <img
            key={it.id}
            src={it.image_url!}
            alt=""
            loading="lazy"
            className="aspect-[2/3] w-full rounded-md object-cover"
          />
        ))}
      </div>
      {/* fade: keep the sentence readable and blend the wall into the page */}
      <div className="absolute inset-0 bg-gradient-to-r from-bg via-bg/85 to-bg/30" />

    </div>
  );
}
