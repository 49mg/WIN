import type { Recommendation } from "@/lib/api";
import { CategoryTag, Poster } from "./Poster";

type Props = {
  rec: Recommendation;
  feedback: boolean | undefined;
  queued: boolean;
  onFeedback: (liked: boolean) => void;
  onQueue: () => void;
  /** featured: the top pick, large. tile: a poster in the grid. */
  variant?: "featured" | "tile";
};

const Icon = {
  up: (
    <svg viewBox="0 0 24 24" aria-hidden className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 10v11H4V10h3Zm0 0 4-7a2 2 0 0 1 3 2l-1 5h6a2 2 0 0 1 2 2.3l-1.4 7A2 2 0 0 1 17.6 21H7" />
    </svg>
  ),
  down: (
    <svg viewBox="0 0 24 24" aria-hidden className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 14V3h3v11h-3Zm0 0-4 7a2 2 0 0 1-3-2l1-5H5a2 2 0 0 1-2-2.3l1.4-7A2 2 0 0 1 6.4 3H17" />
    </svg>
  ),
  save: (
    <svg viewBox="0 0 24 24" aria-hidden className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 3h12v18l-6-4-6 4V3Z" />
    </svg>
  ),
  saved: (
    <svg viewBox="0 0 24 24" aria-hidden className="size-4" fill="currentColor">
      <path d="M6 3h12v18l-6-4-6 4V3Z" />
    </svg>
  ),
};

function Actions({ feedback, queued, onFeedback, onQueue, compact }: Props & { compact: boolean }) {
  const base =
    "inline-flex shrink-0 items-center justify-center gap-1.5 whitespace-nowrap rounded-lg border text-sm font-medium transition-colors disabled:cursor-default";
  const size = compact ? "size-9" : "h-10 px-4";
  const idle = "border-line-strong text-muted hover:border-muted hover:text-fg"; // ghost buttons
  const buttons = [
    {
      label: "More like this",
      icon: Icon.up,
      pressed: feedback === true,
      on: "border-fg bg-fg text-bg",
      click: () => onFeedback(true),
    },
    {
      label: "Not for me",
      icon: Icon.down,
      pressed: feedback === false,
      on: "border-dim bg-dim text-fg",
      click: () => onFeedback(false),
    },
  ];
  return (
    <div className="flex flex-wrap items-center gap-2">
      {buttons.map((b) => (
        <button
          key={b.label}
          type="button"
          aria-pressed={b.pressed}
          aria-label={compact ? b.label : undefined}
          title={compact ? b.label : undefined}
          className={`${base} ${size} ${b.pressed ? b.on : idle}`}
          onClick={b.click}
        >
          {b.icon}
          {!compact && b.label}
        </button>
      ))}
      <button
        type="button"
        disabled={queued}
        aria-label={compact ? (queued ? "In queue" : "Next queue: save for later") : undefined}
        title={compact ? (queued ? "In your queue" : "Save to your Next queue") : undefined}
        className={`${base} ${size} ${queued ? "border-accent text-accent" : idle} ${compact ? "ml-auto" : ""}`}
        onClick={onQueue}
      >
        {queued ? Icon.saved : Icon.save}
        {!compact && (queued ? "In queue" : "Next queue")}
      </button>
    </div>
  );
}

/** Match score bar: high = full orange, mid = faded orange, low = grey. */
function MatchBar({ value, wide }: { value: number; wide: boolean }) {
  const level = value >= 60 ? "high" : value >= 45 ? "mid" : "low";
  const fill = { high: "bg-accent", mid: "bg-accent opacity-60", low: "bg-dim" }[level];
  return (
    <div
      className={`flex items-center gap-2 ${wide ? "max-w-60" : ""}`}
      title={`${value}% match with what you loved`}
    >
      <div className="h-1.5 flex-1 overflow-hidden rounded-[3px] bg-line" aria-hidden>
        <div className={`h-full rounded-[3px] ${fill}`} style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className={`min-w-[2.2rem] text-right text-xs tabular-nums ${level === "low" ? "text-muted" : ""}`}>
        {value}%<span className="sr-only"> match</span>
      </span>
    </div>
  );
}

function Meta({ rec, full }: { rec: Recommendation; full: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
      <CategoryTag item={rec} />
      {rec.year && <span className="tabular-nums">{rec.year}</span>}
      {rec.ai &&
        (full ? (
          <span title="Picked and explained by an AI model">✦ AI pick</span>
        ) : (
          <span title="AI pick: picked and explained by an AI model" aria-label="AI pick">
            ✦
          </span>
        ))}
    </div>
  );
}

/** Some book descriptions arrive with Markdown marks (**bold**); show plain text. */
const plain = (text: string) => text.replace(/\*\*|__|(?<!\w)[*_](?=\S)|(?<=\S)[*_](?!\w)/g, "");

export function RecCard(props: Props) {
  const { rec, variant = "tile" } = props;

  if (variant === "featured") {
    return (
      <article className="grid gap-6 rounded-xl border-[1.5px] border-accent bg-surface p-5 sm:grid-cols-[minmax(0,14rem)_1fr] sm:p-7">
        <Poster item={rec} className="w-40 sm:w-full" />
        <div className="flex min-w-0 flex-col gap-4">
          <span className="self-start rounded-md bg-accent px-2 py-0.5 text-xs font-medium text-accent-ink">
            Your next pick
          </span>
          <h3 className="font-display text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl">
            {rec.title}
          </h3>
          <Meta rec={rec} full />
          <MatchBar value={rec.match} wide />
          <p className="max-w-[60ch] text-lg leading-snug">{rec.reason}</p>
          {rec.description && (
            <p className="line-clamp-3 max-w-[65ch] text-sm leading-relaxed text-muted">
              {plain(rec.description)}
            </p>
          )}
          <div className="mt-auto pt-2">
            <Actions {...props} compact={false} />
          </div>
        </div>
      </article>
    );
  }

  return (
    <article className="flex min-w-0 flex-col gap-3">
      <Poster item={rec} className="w-full" />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <h3 className="line-clamp-2 font-display text-lg font-bold leading-tight">{rec.title}</h3>
        <Meta rec={rec} full={false} />
        <MatchBar value={rec.match} wide={false} />
        <p className="line-clamp-4 text-sm leading-snug text-fg/85">{rec.reason}</p>
      </div>
      <Actions {...props} compact />
    </article>
  );
}
