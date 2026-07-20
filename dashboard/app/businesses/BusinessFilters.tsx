"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function BusinessFilters({
  initial,
}: {
  initial: { q: string; city: string; category: string; confidence_min: string };
}) {
  const router = useRouter();
  const [q, setQ] = useState(initial.q);
  const [city, setCity] = useState(initial.city);
  const [category, setCategory] = useState(initial.category);
  const [confidenceMin, setConfidenceMin] = useState(initial.confidence_min);

  function apply(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (city) params.set("city", city);
    if (category) params.set("category", category);
    if (confidenceMin) params.set("confidence_min", confidenceMin);
    router.push(`/businesses?${params.toString()}`);
  }

  return (
    <form onSubmit={apply} className="flex flex-wrap items-end gap-3 rounded-lg border border-ink-600 bg-ink-900/80 p-4">
      <label className="flex flex-col gap-1 text-xs text-mist-400">
        Search
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Name, city…"
          className="rounded border border-ink-600 bg-ink-850 px-3 py-1.5 text-sm text-mist-100 outline-none focus:border-accent"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-mist-400">
        City
        <input
          value={city}
          onChange={(e) => setCity(e.target.value)}
          placeholder="Austin"
          className="rounded border border-ink-600 bg-ink-850 px-3 py-1.5 text-sm text-mist-100 outline-none focus:border-accent"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-mist-400">
        Category
        <input
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="restaurant_cafe"
          className="rounded border border-ink-600 bg-ink-850 px-3 py-1.5 text-sm text-mist-100 outline-none focus:border-accent"
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-mist-400">
        Min confidence
        <input
          type="number"
          min={0}
          max={100}
          value={confidenceMin}
          onChange={(e) => setConfidenceMin(e.target.value)}
          placeholder="50"
          className="w-24 rounded border border-ink-600 bg-ink-850 px-3 py-1.5 text-sm text-mist-100 outline-none focus:border-accent"
        />
      </label>
      <button
        type="submit"
        className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-ink-950 hover:bg-accent-glow"
      >
        Apply
      </button>
    </form>
  );
}
