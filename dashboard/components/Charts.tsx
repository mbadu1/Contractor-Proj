"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Area,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtPct, fmtUsd, labelCategory } from "@/lib/format";

const GRID = "#1e2738";
const AXIS = "#6b778c";
const TIP_STYLE = {
  backgroundColor: "#111722",
  border: "1px solid #2a3548",
  borderRadius: 6,
  fontSize: 12,
};

export function CategoryBarChart({
  data,
}: {
  data: { category: string; total_revenue: number; share: number }[];
}) {
  const rows = data.slice(0, 12).map((d) => ({
    name: labelCategory(d.category),
    revenue: d.total_revenue,
    share: d.share * 100,
  }));
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fill: AXIS, fontSize: 11 }} tickFormatter={(v) => fmtUsd(v, true)} />
          <YAxis type="category" dataKey="name" width={110} tick={{ fill: AXIS, fontSize: 10 }} />
          <Tooltip
            contentStyle={TIP_STYLE}
            formatter={(v: number) => [fmtUsd(v), "Est. revenue"]}
          />
          <Bar dataKey="revenue" fill="#3d9cf0" radius={[0, 3, 3, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RevenueSeriesChart({
  history,
}: {
  history: {
    period: string;
    point_estimate: number;
    ci_low: number;
    ci_high: number;
    confidence_score: number;
  }[];
}) {
  const data = history.map((h) => ({
    period: h.period,
    point: h.point_estimate,
    ci_low: h.ci_low,
    ci_high: h.ci_high,
    band: h.ci_high - h.ci_low,
    conf: h.confidence_score,
  }));
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ left: 4, right: 8, top: 8, bottom: 0 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="period" tick={{ fill: AXIS, fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: AXIS, fontSize: 10 }} tickFormatter={(v) => fmtUsd(v, true)} />
          <Tooltip
            contentStyle={TIP_STYLE}
            formatter={(v: number, name: string) => {
              if (name === "conf") return [fmtPct(v, 0), "Confidence"];
              return [fmtUsd(v), name === "point" ? "Point" : name];
            }}
          />
          <Area
            type="monotone"
            dataKey="ci_high"
            stroke="transparent"
            fill="#3d9cf0"
            fillOpacity={0.12}
            name="CI high"
          />
          <Area
            type="monotone"
            dataKey="ci_low"
            stroke="transparent"
            fill="#07090d"
            fillOpacity={1}
            name="CI low"
          />
          <Line type="monotone" dataKey="point" stroke="#5eb0ff" strokeWidth={2} dot={false} name="point" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ContributionWaterfall({
  contributions,
}: {
  contributions: Record<string, number>;
}) {
  const rows = Object.entries(contributions)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ name: labelCategory(k), value: v * 100 }));
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 4, right: 16 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fill: AXIS, fontSize: 10 }} unit="%" />
          <YAxis type="category" dataKey="name" width={120} tick={{ fill: AXIS, fontSize: 10 }} />
          <Tooltip contentStyle={TIP_STYLE} formatter={(v: number) => [`${v.toFixed(1)}%`, "Share"]} />
          <Bar dataKey="value" radius={[0, 3, 3, 0]}>
            {rows.map((_, i) => (
              <Cell key={i} fill={i === 0 ? "#5eb0ff" : "#2a6fad"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function IndexedGrowthChart({
  series,
}: {
  series: { name: string; color: string; points: { period: string; index: number }[] }[];
}) {
  const periods = Array.from(
    new Set(series.flatMap((s) => s.points.map((p) => p.period)))
  ).sort();
  const data = periods.map((period) => {
    const row: Record<string, string | number> = { period };
    series.forEach((s) => {
      const pt = s.points.find((p) => p.period === period);
      if (pt) row[s.name] = pt.index;
    });
    return row;
  });

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="period" tick={{ fill: AXIS, fontSize: 10 }} interval="preserveStartEnd" />
          <YAxis tick={{ fill: AXIS, fontSize: 10 }} domain={["auto", "auto"]} />
          <Tooltip contentStyle={TIP_STYLE} />
          {series.map((s) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CalibrationChart({
  bins,
}: {
  bins: { mean_confidence: number; mape: number; interval_coverage: number; label: string }[];
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <ComposedChart data={bins} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fill: AXIS, fontSize: 10 }} />
          <YAxis tick={{ fill: AXIS, fontSize: 10 }} unit="%" />
          <Tooltip contentStyle={TIP_STYLE} />
          <Bar dataKey="mape" fill="#e85d5d" name="MAPE %" radius={[3, 3, 0, 0]} />
          <Line type="monotone" dataKey="mean_confidence" stroke="#5eb0ff" name="Avg confidence" strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SegmentMapeChart({
  rows,
}: {
  rows: { name: string; mape: number; coverage: number }[];
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <BarChart data={rows} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fill: AXIS, fontSize: 10 }} />
          <YAxis tick={{ fill: AXIS, fontSize: 10 }} unit="%" />
          <Tooltip contentStyle={TIP_STYLE} />
          <Bar dataKey="mape" fill="#e8a838" name="MAPE %" radius={[3, 3, 0, 0]} />
          <Bar dataKey="coverage" fill="#3ecf8e" name="Interval coverage %" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
