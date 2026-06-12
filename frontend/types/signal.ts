export interface Signal {
  _id: string;
  signal_id: string;
  symbol: string;
  pair?: string;
  margin_currency?: string;
  direction: 'BUY' | 'SELL';
  status: string;
  entry_range: number[];
  target: number;
  stop_loss: number;
  confidence_score: number;
  leverage: number;
  risk_reward: number | string;
  generated_at: string;
  valid_until_ist?: string;
  pnl_r_multiple?: number | null;
  quality_tier?: 'A' | 'B' | 'C';
  composite_score?: number;
  cloudinary_pdf_url?: string;
  pdf_path?: string;
  chart_path?: string;
  timeframe?: string;
  trade_horizon?: string;
  sl_pct?: number;
  tp_pct?: number;
  live_price_at_signal?: number;
  indicators?: string[];
  confluence_hits?: string[];
  reason_why_token?: string;
  reason_entry?: string;
  reason_monitor?: string;
  outcome?: string;
  closed_at?: string;
  asset_class?: string;
  review_status?: string;
}

export type PdfSource = 'cloudinary' | 'proxy' | 'unavailable';

export interface PdfDownloadInfo {
  url: string | null;
  source: PdfSource;
  label: string;
}
