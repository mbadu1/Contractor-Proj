import { CalibrationChart, SegmentMapeChart } from "@/components/Charts";
import { ErrorState, Panel, Stat } from "@/components/Panel";
import { fetchValidationLatest } from "@/lib/api";
import { fmtPct } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function ModelHealthPage() {
  let report;
  try {
    report = await fetchValidationLatest();
  } catch (e) {
    return <ErrorState message={e instanceof Error ? e.message : String(e)} />;
  }

  const sizeRows = report.segment_metrics
    .filter((s) => s.segment_type === "size_tier")
    .map((s) => ({
      name: s.segment_value,
      mape: s.mape,
      coverage: s.interval_coverage,
    }));

  const calib = report.calibration.map((b) => ({
    label: `${b.confidence_bin_low.toFixed(0)}–${b.confidence_bin_high.toFixed(0)}`,
    mean_confidence: b.mean_confidence,
    mape: b.mape,
    interval_coverage: b.interval_coverage,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-mist-100">Model Health</h1>
        <p className="mt-1 text-sm text-mist-400">
          Validated against hidden ground truth — not just asserted. Model{" "}
          <span className="font-mono text-mist-300">{report.model_version}</span>
          {report.promoted ? " · promoted" : ""}
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Holdout MAPE" value={fmtPct(report.mape)} hint="Lower is better" />
        <Stat label="Median APE" value={fmtPct(report.median_ape)} />
        <Stat
          label="Interval coverage"
          value={fmtPct(report.interval_coverage)}
          hint="Share of truth inside CI"
        />
        <Stat
          label="Mean confidence"
          value={fmtPct(report.mean_confidence, 0)}
          hint={`${report.n_observations.toLocaleString()} observations`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="MAPE by size tier" subtitle="Holdout segments">
          <SegmentMapeChart rows={sizeRows} />
        </Panel>
        <Panel
          title="Calibration"
          subtitle="Higher confidence should mean lower MAPE"
        >
          <CalibrationChart bins={calib} />
        </Panel>
      </div>

      <Panel title="Category segments (worst → best MAPE)">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-ink-600 text-[10px] uppercase tracking-[0.12em] text-mist-400">
                <th className="pb-2 font-medium">Category</th>
                <th className="pb-2 font-medium">n</th>
                <th className="pb-2 font-medium">MAPE</th>
                <th className="pb-2 font-medium">Coverage</th>
                <th className="pb-2 font-medium">Avg conf</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {report.segment_metrics
                .filter((s) => s.segment_type === "category")
                .slice()
                .sort((a, b) => b.mape - a.mape)
                .slice(0, 15)
                .map((s) => (
                  <tr key={s.segment_value}>
                    <td className="py-2 capitalize text-mist-200">
                      {s.segment_value.replace(/_/g, " ")}
                    </td>
                    <td className="py-2 font-mono text-mist-400">{s.n_observations}</td>
                    <td className="py-2 font-mono text-mist-100">{fmtPct(s.mape)}</td>
                    <td className="py-2 font-mono text-mist-300">{fmtPct(s.interval_coverage)}</td>
                    <td className="py-2 font-mono text-mist-300">{fmtPct(s.mean_confidence, 0)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {report.notes && (
        <p className="text-xs text-mist-400">Notes: {report.notes}</p>
      )}
    </div>
  );
}
