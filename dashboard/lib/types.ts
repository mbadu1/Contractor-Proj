/** Shared types mirroring the RevWatch API. */

export interface Estimate {
  period: string;
  point_estimate: number;
  ci_low: number;
  ci_high: number;
  confidence_score: number;
  signal_contributions: Record<string, number>;
  model_version: string;
}

export interface Business {
  id: string;
  name: string;
  category: string;
  country: string;
  city: string;
  latitude: number;
  longitude: number;
  size_tier: string;
  channels: string[];
  latest_estimate: Estimate | null;
}

export interface BusinessEstimateDetail {
  business: Business;
  current: Estimate | null;
  history: Estimate[];
}

export interface CategoryRevenue {
  category: string;
  total_revenue: number;
  business_count: number;
  share: number;
}

export interface CityDensity {
  city: string;
  business_count: number;
  total_revenue: number;
  latitude: number;
  longitude: number;
}

export interface MarketSummary {
  country: string;
  model_version: string;
  period: string;
  business_count: number;
  total_estimated_revenue: number;
  hhi: number;
  revenue_by_category: CategoryRevenue[];
  commercial_density_by_city: CityDensity[];
}

export interface RankingItem {
  key: string;
  label: string;
  value: number;
  secondary?: number | null;
}

export interface Rankings {
  model_version: string;
  period: string;
  top_categories_by_revenue: RankingItem[];
  top_cities_by_revenue: RankingItem[];
  growth_leaders: RankingItem[];
  growth_decliners: RankingItem[];
}

export interface SegmentMetrics {
  segment_type: string;
  segment_value: string;
  n_observations: number;
  mape: number;
  interval_coverage: number;
  median_ape: number;
  mean_confidence: number;
}

export interface CalibrationBin {
  confidence_bin_low: number;
  confidence_bin_high: number;
  n_observations: number;
  mean_confidence: number;
  mape: number;
  interval_coverage: number;
}

export interface ValidationLatest {
  model_version: string;
  n_observations: number;
  mape: number;
  median_ape: number;
  interval_coverage: number;
  mean_confidence: number;
  promoted: boolean;
  notes: string;
  segment_metrics: SegmentMetrics[];
  calibration: CalibrationBin[];
}

export interface Paginated<T> {
  data: T[];
  meta: { total: number; limit: number; offset: number };
}
