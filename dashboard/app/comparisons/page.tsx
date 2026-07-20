import { ComparisonsClient } from "./ComparisonsClient";
import { ErrorState } from "@/components/Panel";
import { fetchBusinesses, fetchMarketSummary } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ComparisonsPage() {
  try {
    const [bizPage, market] = await Promise.all([
      fetchBusinesses({ limit: 80, confidence_min: 40 }),
      fetchMarketSummary("US"),
    ]);
    return (
      <ComparisonsClient
        businesses={bizPage.data}
        categories={market.revenue_by_category.map((c) => c.category)}
      />
    );
  } catch (e) {
    return <ErrorState message={e instanceof Error ? e.message : String(e)} />;
  }
}
