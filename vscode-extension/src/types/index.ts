export interface LineStat {
  line_number: number;
  model: string;
  call_count: number;
  total_cost: number;
  avg_cost_per_call: number;
  avg_input_tokens: number;
  avg_output_tokens: number;
  avg_latency_ms: number;
  cache_hits: number;
}

export interface FileStatsResponse {
  file_path: string;
  total_file_calls: number;
  total_file_spend: number;
  line_stats: LineStat[];
}

export interface ForecastResponse {
  has_enough_data: boolean;
  message?: string;
  total_spend: number;
  spend_today: number;
  daily_average: number;
  projected_monthly: number;
  budget: number;
  budget_remaining: number;
  over_budget?: boolean;
}

export interface WarningItem {
  id: string;
  severity: 'WARNING' | 'INFO' | 'ERROR';
  title: string;
  message: string;
  code: string;
}

export interface FeatureAttributionItem {
  feature: string;
  call_count: number;
  avg_cost_per_call: number;
  total_cost: number;
  total_savings: number;
  cache_hit_rate: number;
  avg_latency_ms: number;
}

export interface FeatureResponse {
  features: FeatureAttributionItem[];
  recommendations: any[];
}
