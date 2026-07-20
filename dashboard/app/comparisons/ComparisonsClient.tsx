"use client";

import { useEffect, useMemo, useState } from "react";
import { IndexedGrowthChart } from "@/components/Charts";
import { Panel } from "@/components/Panel";
import { getApiBase } from "@/lib/api";
import type { Business, BusinessEstimateDetail } from "@/lib/types";
import { labelCategory } from "@/lib/format";

const COLORS = ["#5eb0ff", "#3ecf8e", "#e8a838", "#e85d5d", "#b388ff"];

export function ComparisonsClient({
  businesses,
  categories,
}: {
  businesses: Business[];
  categories: string[];
}) {
  const [mode, setMode] = useState<"business" | "category">("business");
  const [selectedBiz, setSelectedBiz] = useState<string[]>([]);
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [series, setSeries] = useState<
    { name: string; color: string; points: { period: string; index: number }[] }[]
  >([]);
  const [loading, setLoading] = useState(false);

  const bizOptions = useMemo(
    () => businesses.filter((b) => b.latest_estimate).slice(0, 60),
    [businesses]
  );

  function toggleBiz(id: string) {
    setSelectedBiz((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : prev.length < 4 ? [...prev, id] : prev
    );
  }

  function toggleCat(cat: string) {
    setSelectedCats((prev) =>
      prev.includes(cat) ? prev.filter((x) => x !== cat) : prev.length < 4 ? [...prev, cat] : prev
    );
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        if (mode === "business" && selectedBiz.length >= 2) {
          const details = await Promise.all(
            selectedBiz.map(async (id) => {
              const res = await fetch(`${getApiBase()}/businesses/${id}/estimate`);
              if (!res.ok) throw new Error(await res.text());
              return res.json() as Promise<BusinessEstimateDetail>;
            })
          );
          if (cancelled) return;
          setSeries(
            details.map((d, i) => {
              const base = d.history[0]?.point_estimate || 1;
              return {
                name: d.business.name,
                color: COLORS[i % COLORS.length],
                points: d.history.map((h) => ({
                  period: h.period,
                  index: (h.point_estimate / base) * 100,
                })),
              };
            })
          );
        } else if (mode === "category" && selectedCats.length >= 2) {
          // Approximate category index from businesses in each category
          const byCat = selectedCats.map((cat, i) => {
            const members = bizOptions.filter((b) => b.category === cat).slice(0, 3);
            return { cat, i, members };
          });
          const loaded = await Promise.all(
            byCat.map(async ({ cat, i, members }) => {
              if (!members.length) return { name: labelCategory(cat), color: COLORS[i], points: [] as { period: string; index: number }[] };
              const histories = await Promise.all(
                members.map(async (m) => {
                  const res = await fetch(`${getApiBase()}/businesses/${m.id}/estimate`);
                  const d = (await res.json()) as BusinessEstimateDetail;
                  return d.history;
                })
              );
              const periods = histories[0]?.map((h) => h.period) || [];
              const avg = periods.map((period, idx) => {
                const vals = histories.map((h) => h[idx]?.point_estimate || 0);
                return vals.reduce((a, b) => a + b, 0) / vals.length;
              });
              const base = avg[0] || 1;
              return {
                name: labelCategory(cat),
                color: COLORS[i % COLORS.length],
                points: periods.map((period, idx) => ({
                  period,
                  index: (avg[idx] / base) * 100,
                })),
              };
            })
          );
          if (cancelled) return;
          setSeries(loaded);
        } else {
          setSeries([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [mode, selectedBiz, selectedCats, bizOptions]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-mist-100">Comparisons</h1>
        <p className="mt-1 text-sm text-mist-400">
          Pick 2–4 businesses or categories — curves indexed to 100 at first period
        </p>
      </div>

      <div className="flex gap-2">
        {(["business", "category"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded px-3 py-1.5 text-sm capitalize ${
              mode === m ? "bg-ink-700 text-accent-glow" : "bg-ink-850 text-mist-300"
            }`}
          >
            {m}
          </button>
        ))}
      </div>

      <Panel title={mode === "business" ? "Select businesses" : "Select categories"}>
        <div className="flex max-h-40 flex-wrap gap-2 overflow-y-auto">
          {mode === "business"
            ? bizOptions.map((b) => {
                const on = selectedBiz.includes(b.id);
                return (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => toggleBiz(b.id)}
                    className={`rounded border px-2 py-1 text-xs ${
                      on
                        ? "border-accent bg-accent/15 text-accent-glow"
                        : "border-ink-600 text-mist-300 hover:border-ink-500"
                    }`}
                  >
                    {b.name}
                  </button>
                );
              })
            : categories.map((c) => {
                const on = selectedCats.includes(c);
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => toggleCat(c)}
                    className={`rounded border px-2 py-1 text-xs capitalize ${
                      on
                        ? "border-accent bg-accent/15 text-accent-glow"
                        : "border-ink-600 text-mist-300 hover:border-ink-500"
                    }`}
                  >
                    {labelCategory(c)}
                  </button>
                );
              })}
        </div>
      </Panel>

      <Panel
        title="Indexed growth"
        subtitle={loading ? "Loading…" : "100 = first month in series"}
      >
        {series.length >= 2 ? (
          <>
            <IndexedGrowthChart series={series} />
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-mist-400">
              {series.map((s) => (
                <span key={s.name} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
                  {s.name}
                </span>
              ))}
            </div>
          </>
        ) : (
          <p className="py-10 text-center text-sm text-mist-400">Select at least two items to compare</p>
        )}
      </Panel>
    </div>
  );
}
