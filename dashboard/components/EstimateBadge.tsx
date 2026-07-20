import type { Estimate } from "@/lib/types";
import { confidenceTone, fmtPct, fmtUsd } from "@/lib/format";

/** Never render a bare revenue number — always CI + confidence. */
export function EstimateBadge({ estimate, compact = false }: { estimate: Estimate; compact?: boolean }) {
  const tone = confidenceTone(estimate.confidence_score);
  const toneClass =
    tone === "good" ? "text-good border-good/40 bg-good/10" :
    tone === "warn" ? "text-warn border-warn/40 bg-warn/10" :
    "text-bad border-bad/40 bg-bad/10";

  return (
    <div className="inline-flex flex-col gap-0.5">
      <div className="font-mono text-mist-100 tabular-nums">
        {fmtUsd(estimate.point_estimate, compact)}
        <span className="ml-2 text-xs text-mist-400">
          [{fmtUsd(estimate.ci_low, true)}–{fmtUsd(estimate.ci_high, true)}]
        </span>
      </div>
      <span className={`w-fit rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${toneClass}`}>
        conf {fmtPct(estimate.confidence_score, 0)}
      </span>
    </div>
  );
}
