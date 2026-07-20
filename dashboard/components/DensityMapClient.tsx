"use client";

import dynamic from "next/dynamic";
import type { CityDensity } from "@/lib/types";

const DensityMapInner = dynamic(
  () => import("./DensityMap").then((m) => m.DensityMap),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-80 items-center justify-center rounded-md border border-ink-600 bg-ink-850 text-sm text-mist-400">
        Loading map…
      </div>
    ),
  }
);

export function DensityMapClient({ cities }: { cities: CityDensity[] }) {
  return <DensityMapInner cities={cities} />;
}
