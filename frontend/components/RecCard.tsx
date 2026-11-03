import type { Recommendation } from "@/lib/api";
import { CategoryTag, Poster } from "./Poster";

export function RecCard({
  rec,
  feedback,
  queued,
  onFeedback,
  onQueue,
}: {
  rec: Recommendation;
  feedback: boolean | undefined;
  queued: boolean;
  onFeedback: (liked: boolean) => void;
  onQueue: () => void;
}) {
  const btn = "rounded-md border px-2.5 py-1 text-xs transition-colors";
  const idle = "border-line text-muted hover:border-fg hover:text-fg";
  return (
    <article className="flex gap-4 border-b border-line py-4 last:border-0">
      <Poster item={rec} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="truncate font-semibold">
            {rec.title}
            {rec.year && <span className="ml-1.5 font-normal text-muted">{rec.year}</span>}
          </h3>
          <span className="shrink-0 text-xs tabular-nums text-ok">{rec.match}% match</span>
        </div>
        <CategoryTag item={rec} />
        <p className="mt-1 text-sm">{rec.reason}</p>
        {rec.description && (
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{rec.description}</p>
        )}
        <div className="mt-2.5 flex gap-2">
          <button
            type="button"
            aria-pressed={feedback === true}
            className={`${btn} ${feedback === true ? "border-ok bg-ok text-accent-ink" : idle}`}
            onClick={() => onFeedback(true)}
          >
            👍 More like this
          </button>
          <button
            type="button"
            aria-pressed={feedback === false}
            className={`${btn} ${feedback === false ? "border-fg bg-fg text-bg" : idle}`}
            onClick={() => onFeedback(false)}
          >
            👎 Not for me
          </button>
          <button
            type="button"
            disabled={queued}
            className={`${btn} ${queued ? "border-accent text-accent" : idle}`}
            onClick={onQueue}
          >
            {queued ? "✓ In queue" : "+ Next queue"}
          </button>
        </div>
      </div>
    </article>
  );
}
