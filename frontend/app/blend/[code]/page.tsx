"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import { Poster } from "@/components/Poster";
import { RecCard } from "@/components/RecCard";
import { ApiError, getShared, userApi, type Recommendation, type SharedTaste } from "@/lib/api";
import { useUser } from "@/lib/user";

export default function Blend({ params }: { params: Promise<{ code: string }> }) {
  const { code } = use(params);
  const { userId, liked, feedback, vote, queue, addToQueue } = useUser();
  const [them, setThem] = useState<SharedTaste | null>(null);
  const [picks, setPicks] = useState<Recommendation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getShared(code)
      .then(setThem)
      .catch(() => setError("This blend link doesn't exist (anymore)."));
  }, [code]);

  useEffect(() => {
    if (!userId || !them || liked.length === 0) return;
    userApi
      .blend(userId, code)
      .then(setPicks)
      .catch((e) => setError(e instanceof ApiError && e.status === 400 ? e.message : "Could not blend right now."));
    // re-blend when what you loved changes
  }, [userId, them, code, liked]);

  const queued = new Set(queue.map((q) => q.item.id));

  return (
    <div className="flex flex-col gap-8 pb-8 pt-6 sm:pt-12">
      <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-6xl">
        Your blend
      </h1>
      {them && (
        <div className="flex flex-col gap-3">
          <p className="max-w-[60ch] text-lg text-muted">
            Your friend loved {them.liked.slice(0, 4).map((i) => i.title).join(", ")}
            {them.liked.length > 4 ? "…" : ""}. Here is what you could enjoy together.
          </p>
          <div className="flex -space-x-2" aria-hidden>
            {them.liked.slice(0, 6).map((i) => (
              <Poster key={i.id} item={i} className="w-10 rounded-md ring-2 ring-bg" />
            ))}
          </div>
        </div>
      )}
      {error && <p className="text-sm text-danger">{error}</p>}
      {them && liked.length === 0 && (
        <p className="text-sm text-muted">
          Add a few things <em>you</em> loved on{" "}
          <Link href="/" className="text-accent underline">
            Discover
          </Link>
          , then come back to this link.
        </p>
      )}
      {picks && picks.length > 0 && (
        <section className="flex flex-col gap-6" aria-label="Picks for both of you">
          {picks.map((r, i) =>
            i === 0 ? (
              <RecCard
                key={r.id}
                rec={r}
                variant="featured"
                feedback={feedback[r.id]?.liked}
                queued={queued.has(r.id)}
                onFeedback={(up) => vote(r, up)}
                onQueue={() => addToQueue(r)}
              />
            ) : null,
          )}
          <div className="grid grid-cols-2 gap-x-4 gap-y-10 sm:gap-x-5 md:grid-cols-5">
            {picks.slice(1).map((r) => (
              <RecCard
                key={r.id}
                rec={r}
                feedback={feedback[r.id]?.liked}
                queued={queued.has(r.id)}
                onFeedback={(up) => vote(r, up)}
                onQueue={() => addToQueue(r)}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
