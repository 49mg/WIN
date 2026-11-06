"use client";

import Link from "next/link";
import { useState } from "react";
import { userApi } from "@/lib/api";
import { useUser } from "@/lib/user";

export default function BlendHome() {
  const { userId, liked, loaded } = useUser();
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createLink() {
    if (!userId) return;
    try {
      const { code } = await userApi.share(userId);
      setLink(`${window.location.origin}/blend/${code}`);
    } catch {
      setError("Could not create your link. Is the WIN API running?");
    }
  }

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false); // clipboard blocked: the link is shown as text to copy by hand
    }
  }

  return (
    <div className="flex max-w-3xl flex-col gap-6 pb-8 pt-6 sm:pt-12">
      <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
        Blend with a friend
      </h1>
      <p className="max-w-[60ch] text-lg text-muted">
        Send your link to a friend. When they open it, WIN finds things you would <em>both</em>{" "}
        enjoy, and says which of your favourites each pick connects to. The link only shows what
        you loved; nobody can change your picks with it.
      </p>
      {loaded && liked.length === 0 && (
        <p className="text-sm text-muted">
          First add a few things you loved on{" "}
          <Link href="/" className="text-accent underline">
            Discover
          </Link>
          .
        </p>
      )}
      {!link ? (
        <button
          type="button"
          disabled={!userId || liked.length === 0}
          onClick={createLink}
          className="self-start rounded-lg bg-fg px-7 py-3.5 font-display text-lg font-bold text-bg transition-opacity hover:opacity-90 disabled:opacity-35"
        >
          Create my blend link
        </button>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <input
            id="blend-link"
            readOnly
            value={link}
            onFocus={(e) => e.target.select()}
            className="min-w-0 flex-1 rounded-lg border border-line-strong bg-surface px-4 py-3 text-sm"
          />
          <button type="button" onClick={copy} className="rounded-lg bg-fg px-5 py-3 text-sm font-medium text-bg hover:opacity-85">
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      )}
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}
