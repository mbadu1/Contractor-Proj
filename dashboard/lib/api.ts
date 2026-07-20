import type {
  Business,
  BusinessEstimateDetail,
  MarketSummary,
  Paginated,
  Rankings,
  ValidationLatest,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function apiGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const url = new URL(path, API_URL);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
    });
  }
  const res = await fetch(url.toString(), { next: { revalidate: 30 } });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function getApiBase(): string {
  return API_URL;
}

export async function fetchMarketSummary(country = "US"): Promise<MarketSummary> {
  return apiGet(`/markets/${country}/summary`);
}

export async function fetchRankings(limit = 10): Promise<Rankings> {
  return apiGet("/rankings", { limit });
}

export async function fetchBusinesses(params: {
  city?: string;
  category?: string;
  confidence_min?: number;
  revenue_min?: number;
  revenue_max?: number;
  limit?: number;
  offset?: number;
}): Promise<Paginated<Business>> {
  return apiGet("/businesses", params);
}

export async function fetchBusinessEstimate(id: string): Promise<BusinessEstimateDetail> {
  return apiGet(`/businesses/${id}/estimate`);
}

export async function fetchValidationLatest(): Promise<ValidationLatest> {
  return apiGet("/validation/latest");
}

export async function fetchHealth(): Promise<{
  status: string;
  businesses: number;
  promoted_model: string | null;
}> {
  return apiGet("/health");
}
