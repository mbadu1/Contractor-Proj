export function Panel({
  title,
  subtitle,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-ink-600 bg-ink-900/80 ${className}`}>
      {(title || subtitle) && (
        <div className="border-b border-ink-600 px-4 py-3">
          {title && <h2 className="text-sm font-medium text-mist-100">{title}</h2>}
          {subtitle && <p className="mt-0.5 text-xs text-mist-400">{subtitle}</p>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-ink-600 bg-ink-850 px-4 py-3">
      <div className="text-[10px] uppercase tracking-[0.15em] text-mist-400">{label}</div>
      <div className="mt-1 font-mono text-xl text-mist-100 tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-xs text-mist-400">{hint}</div>}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-bad/40 bg-bad/10 px-4 py-6 text-sm text-bad">
      <p className="font-medium">Could not load data</p>
      <p className="mt-1 text-mist-300">{message}</p>
      <p className="mt-3 text-xs text-mist-400">
        Is the API running? Try <code className="text-mist-200">make api</code>
      </p>
    </div>
  );
}
