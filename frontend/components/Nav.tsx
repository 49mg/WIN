"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Discover" },
  { href: "/me", label: "My taste" },
  { href: "/blend", label: "Blend" },
];

export function Nav() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <nav aria-label="Main" className="flex gap-1 text-sm">
      {LINKS.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          aria-current={active(l.href) ? "page" : undefined}
          className={`rounded-full px-3 py-1.5 transition-colors ${
            active(l.href) ? "bg-fg text-bg" : "text-muted hover:text-fg"
          }`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}
