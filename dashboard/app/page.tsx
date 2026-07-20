import { CategoryBarChart } from "@/components/Charts";
import { DensityMapClient } from "@/components/DensityMapClient";
import { ErrorState, Panel, Stat } from "@/components/Panel";
import { fetchMarketSummary, fetchRankings } from "@/lib/api";
import { fmtPct, fmtUsd, labelCategory } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function MarketOverviewPage() {
  let market;
  let rankings;
  try {
    [market, rankings] = await Promise.all([
      fetchMarketSummary("US"),
      fetchRankings(8),
    ]);
  } catch (e) {
    return <ErrorState message={e instanceof Error ? e.message : String(e)} />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-mist-100">Market Overview</h1>
        <p className="mt-1 text-sm text-mist-400">
          US commercial density and estimated revenue — period {market.period} · model{" "}
          <span className="font-mono text-mist-300">{market.model_version}</span>
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Businesses" value={market.business_count.toLocaleString()} />
        <Stat
          label="Est. total revenue"
          value={fmtUsd(market.total_estimated_revenue, true)}
          hint={`Period ${market.period}`}
        />
        <Stat
          label="Concentration (HHI)"
          value={market.hhi.toFixed(0)}
          hint={market.hhi < 1500 ? "Competitive" : market.hhi < 2500 ? "Moderate" : "Concentrated"}
        />
        <Stat
          label="Top category share"
          value={fmtPct((market.revenue_by_category[0]?.share ?? 0) * 100)}
          hint={labelCategory(market.revenue_by_category[0]?.category ?? "—")}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel
          title="Commercial density"
          subtitle="Circle size = business count by city"
        >
          <DensityMapClient cities={market.commercial_density_by_city} />
        </Panel>
        <Panel title="Revenue by category" subtitle="Point estimates summed for the period">
          <CategoryBarChart data={market.revenue_by_category} />
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Top cities by estimated revenue">
          <ul className="divide-y divide-ink-600">
            {rankings.top_cities_by_revenue.map((r, i) => (
              <li key={r.key} className="flex items-center justify-between py-2 text-sm">
                <span className="text-mist-300">
                  <span className="mr-2 font-mono text-mist-400">{i + 1}.</span>
                  {r.label}
                </span>
                <span className="font-mono text-mist-100">{fmtUsd(r.value, true)}</span>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Growth leaders (MoM %)" subtitle="Indexed on latest vs prior month point estimates">
          <ul className="divide-y divide-ink-600">
            {rankings.growth_leaders.map((r) => (
              <li key={r.key} className="flex items-center justify-between py-2 text-sm">
                <span className="truncate text-mist-300">{r.label}</span>
                <span className="font-mono text-good">
                  {r.value >= 0 ? "+" : ""}
                  {fmtPct(r.value)}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
