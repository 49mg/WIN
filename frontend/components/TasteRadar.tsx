/** Radar of the user's top genres. Values are genre counts scaled to the biggest one. */
export function TasteRadar({ genres }: { genres: string[] }) {
  const counts = new Map<string, number>();
  for (const g of genres) counts.set(g, (counts.get(g) ?? 0) + 1);
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);

  if (top.length < 3) {
    return (
      <p className="py-6 text-sm text-muted">
        Add a few more things you loved (or 👍 some picks) to see your taste profile.
      </p>
    );
  }

  const max = top[0][1];
  const c = 110;
  const r = 80;
  const point = (i: number, scale: number) => {
    const a = (Math.PI * 2 * i) / top.length - Math.PI / 2;
    return [c + Math.cos(a) * r * scale, c + Math.sin(a) * r * scale] as const;
  };
  const ring = (scale: number) => top.map((_, i) => point(i, scale).join(",")).join(" ");
  const shape = top.map(([, n], i) => point(i, n / max).join(",")).join(" ");

  return (
    <svg
      viewBox="-80 0 380 220"
      className="mx-auto w-full max-w-md"
      role="img"
      aria-label={`Taste profile: ${top.map(([g, n]) => `${g} ${n}`).join(", ")}`}
    >
      {[1, 0.5].map((s) => (
        <polygon key={s} points={ring(s)} fill="none" stroke="var(--line)" />
      ))}
      {top.map((_, i) => {
        const [x, y] = point(i, 1);
        return <line key={i} x1={c} y1={c} x2={x} y2={y} stroke="var(--line)" />;
      })}
      <polygon points={shape} fill="var(--accent)" fillOpacity={0.22} stroke="var(--accent)" strokeWidth={2} />
      {top.map(([g], i) => {
        const [x, y] = point(i, 1.2);
        const anchor = Math.abs(x - c) < 5 ? "middle" : x > c ? "start" : "end";
        return (
          <text key={g} x={x} y={y + 4} textAnchor={anchor} fontSize={11} fill="var(--muted)">
            {g}
          </text>
        );
      })}
    </svg>
  );
}
