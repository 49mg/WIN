"use client";

import { useEffect, useState } from "react";
import { getMetrics, type Metrics, type Rate } from "@/lib/api";

const pct = (r: Rate) => `${(r.value * 100).toFixed(1)}%`;
const ci = (r: Rate) => `${(r.low * 100).toFixed(1)}–${(r.high * 100).toFixed(1)}%`;
const ARM_LABEL = { llm: "Engine + AI re-ranking", engine: "Engine only (holdout)" };

export default function Stats() {
  const [m, setM] = useState<Metrics | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    getMetrics().then(setM).catch(() => setError(true));
  }, []);

  return (
    <div className="flex flex-col gap-10 pb-8 pt-6">
      <section className="flex flex-col gap-3">
        <h1 className="font-display text-3xl font-extrabold tracking-tight">How well does WIN work?</h1>
        <p className="max-w-prose text-sm text-muted">
          Live A/B test. Each new visitor is put in one group at random: most get AI re-ranking,
          some get the engine only. Rates are per card shown; the range is a 95% confidence
          interval, so groups only really differ when their ranges don&apos;t overlap.
        </p>
        {error && <p className="text-sm text-[var(--movie)]">Could not load the numbers.</p>}
        {m && m.results.length === 0 && (
          <p className="text-sm text-muted">No usage yet. Numbers appear after the first picks.</p>
        )}
        {m && m.results.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full text-left text-sm tabular-nums">
              <thead className="text-xs uppercase tracking-wider text-muted">
                <tr>
                  {["Group", "Mode", "Users", "Cards shown", "👍 rate", "Queued", "👎 rate"].map((h) => (
                    <th key={h} className="px-3 py-2 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {m.results.map((r) => (
                  <tr key={r.arm + r.mode}>
                    <td className="px-3 py-2">{ARM_LABEL[r.arm]}</td>
                    <td className="px-3 py-2">{r.mode === "titles" ? "By titles" : "By vibe"}</td>
                    <td className="px-3 py-2">{r.users}</td>
                    <td className="px-3 py-2">{r.impressions}</td>
                    {[r.like_rate, r.queue_rate, r.dislike_rate].map((rate, i) => (
                      <td key={i} className="px-3 py-2">
                        {pct(rate)} <span className="text-xs text-muted">({ci(rate)})</span>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-display text-2xl font-bold">Offline results (MovieLens)</h2>
        <p className="max-w-prose text-sm text-muted">
          Before any real users: MovieLens users each gave their last 5 liked movies, and we
          checked whether the picks matched what they liked next (581 users for search, 100 for the
          AI tests to keep costs low).
        </p>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-left text-sm tabular-nums">
            <thead className="text-xs uppercase tracking-wider text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Change</th>
                <th className="px-3 py-2 font-medium">Recall</th>
                <th className="px-3 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              <tr>
                <td className="px-3 py-2">Hybrid search (keywords + vectors)</td>
                <td className="px-3 py-2">recall@30 0.090 → 0.111</td>
                <td className="px-3 py-2">+24%, significant</td>
              </tr>
              <tr>
                <td className="px-3 py-2">AI re-ranking of the top 30</td>
                <td className="px-3 py-2">recall@10 0.032 → 0.046</td>
                <td className="px-3 py-2">+43%, significant (100 users)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">AI alone, no engine</td>
                <td className="px-3 py-2">recall@10 0.032 → 0.046</td>
                <td className="px-3 py-2">not significant; 11.5% of titles not in the catalog</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
