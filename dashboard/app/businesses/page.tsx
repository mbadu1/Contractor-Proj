import Link from "next/link";
import { EstimateBadge } from "@/components/EstimateBadge";
import { ErrorState, Panel } from "@/components/Panel";
import { fetchBusinesses } from "@/lib/api";
import { labelCategory } from "@/lib/format";
import { BusinessFilters } from "./BusinessFilters";

export const dynamic = "force-dynamic";

export default async function BusinessesPage({
  searchParams,
}: {
  searchParams: Record<string, string | undefined>;
}) {
  const city = searchParams.city;
  const category = searchParams.category;
  const confidence_min = searchParams.confidence_min
    ? Number(searchParams.confidence_min)
    : undefined;
  const q = searchParams.q?.toLowerCase();
  const limit = 40;
  const offset = Number(searchParams.offset || 0);

  let page;
  try {
    page = await fetchBusinesses({
      city,
      category,
      confidence_min,
      limit: 200,
      offset: 0,
    });
  } catch (e) {
    return <ErrorState message={e instanceof Error ? e.message : String(e)} />;
  }

  let rows = page.data;
  if (q) {
    rows = rows.filter(
      (b) =>
        b.name.toLowerCase().includes(q) ||
        b.city.toLowerCase().includes(q) ||
        b.category.toLowerCase().includes(q)
    );
  }
  const total = q ? rows.length : page.meta.total;
  const slice = rows.slice(offset, offset + limit);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-mist-100">Business Explorer</h1>
        <p className="mt-1 text-sm text-mist-400">
          Search and filter — every estimate shows interval + confidence
        </p>
      </div>

      <BusinessFilters
        initial={{
          q: searchParams.q || "",
          city: city || "",
          category: category || "",
          confidence_min: searchParams.confidence_min || "",
        }}
      />

      <Panel subtitle={`${total.toLocaleString()} matching · showing ${slice.length}`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-ink-600 text-[10px] uppercase tracking-[0.12em] text-mist-400">
                <th className="pb-2 font-medium">Business</th>
                <th className="pb-2 font-medium">Category</th>
                <th className="pb-2 font-medium">City</th>
                <th className="pb-2 font-medium">Size</th>
                <th className="pb-2 font-medium">Latest estimate</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-ink-700">
              {slice.map((b) => (
                <tr key={b.id} className="hover:bg-ink-850/80">
                  <td className="py-3 pr-3">
                    <Link
                      href={`/businesses/${b.id}`}
                      className="font-medium text-accent-glow hover:underline"
                    >
                      {b.name}
                    </Link>
                  </td>
                  <td className="py-3 pr-3 capitalize text-mist-300">{labelCategory(b.category)}</td>
                  <td className="py-3 pr-3 text-mist-300">{b.city}</td>
                  <td className="py-3 pr-3 font-mono text-xs text-mist-400">{b.size_tier}</td>
                  <td className="py-3">
                    {b.latest_estimate ? (
                      <EstimateBadge estimate={b.latest_estimate} compact />
                    ) : (
                      <span className="text-mist-400">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
