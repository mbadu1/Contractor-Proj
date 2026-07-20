import Link from "next/link";
import { ContributionWaterfall, RevenueSeriesChart } from "@/components/Charts";
import { EstimateBadge } from "@/components/EstimateBadge";
import { ErrorState, Panel, Stat } from "@/components/Panel";
import { fetchBusinessEstimate } from "@/lib/api";
import { labelCategory } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function BusinessDetailPage({
  params,
}: {
  params: { id: string };
}) {
  let detail;
  try {
    detail = await fetchBusinessEstimate(params.id);
  } catch (e) {
    return <ErrorState message={e instanceof Error ? e.message : String(e)} />;
  }

  const { business, current, history } = detail;

  return (
    <div className="space-y-6">
      <div>
        <Link href="/businesses" className="text-xs text-mist-400 hover:text-accent-glow">
          ← Business Explorer
        </Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-mist-100">{business.name}</h1>
        <p className="mt-1 text-sm capitalize text-mist-400">
          {labelCategory(business.category)} · {business.city}, {business.country} ·{" "}
          {business.size_tier}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-ink-600 bg-ink-850 px-4 py-3 sm:col-span-2">
          <div className="text-[10px] uppercase tracking-[0.15em] text-mist-400">
            Current estimate {current ? `(${current.period})` : ""}
          </div>
          <div className="mt-2">
            {current ? (
              <EstimateBadge estimate={current} />
            ) : (
              <span className="text-mist-400">No estimate</span>
            )}
          </div>
        </div>
        <Stat label="Channels" value={business.channels.join(", ")} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Revenue time series"
          subtitle="Point estimate with confidence interval band"
        >
          {history.length ? (
            <RevenueSeriesChart history={history} />
          ) : (
            <p className="text-sm text-mist-400">No history</p>
          )}
        </Panel>
        <Panel title="Signal contributions" subtitle="Share of model attribution for current period">
          {current && Object.keys(current.signal_contributions).length ? (
            <ContributionWaterfall contributions={current.signal_contributions} />
          ) : (
            <p className="text-sm text-mist-400">No contribution data</p>
          )}
        </Panel>
      </div>
    </div>
  );
}
