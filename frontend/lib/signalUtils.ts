import type { PdfDownloadInfo, Signal } from '../types/signal';

const IST_TIMEZONE = 'Asia/Kolkata';

export function parsePair(pair: string): { base: string; quote: string } {
  const raw = pair.startsWith('B-') ? pair.slice(2) : pair;
  if (raw.includes('_')) {
    const [base, quote] = raw.split('_', 2);
    return { base: base.toUpperCase(), quote: quote.toUpperCase() };
  }
  return { base: raw.toUpperCase(), quote: 'USDT' };
}

export function toTradingViewSymbol(signal: Signal): string {
  if (signal.pair) {
    const { base, quote } = parsePair(signal.pair);
    return `BINANCE:${base}${quote}`;
  }
  const quote = signal.margin_currency || 'USDT';
  return `BINANCE:${signal.symbol}${quote}`;
}

export function toTradingViewInterval(timeframe?: string): string {
  switch (timeframe) {
    case '15m':
      return '15';
    case '1h':
      return '60';
    case '4h':
      return '240';
    case '1d':
      return 'D';
    default:
      return '60';
  }
}

export function formatGeneratedAt(iso: string): { relative: string; absolute: string } {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return { relative: 'Unknown', absolute: '—' };
  }

  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  let relative: string;
  if (diffMins < 1) relative = 'Just now';
  else if (diffMins < 60) relative = `${diffMins}m ago`;
  else if (diffHours < 24) relative = `${diffHours}h ago`;
  else if (diffDays < 7) relative = `${diffDays}d ago`;
  else relative = date.toLocaleDateString('en-IN', { timeZone: IST_TIMEZONE });

  const absolute = date.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });

  return { relative, absolute };
}

export function formatIstDate(iso?: string): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('en-IN', {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

export function extractPdfFilename(pdfPath?: string): string | null {
  if (!pdfPath) return null;
  const filename = pdfPath.split('/').pop() || pdfPath.split('\\').pop();
  return filename || null;
}

export function getPdfDownloadInfo(signal: Signal): PdfDownloadInfo {
  if (signal.cloudinary_pdf_url) {
    return {
      url: signal.cloudinary_pdf_url,
      source: 'cloudinary',
      label: 'Cloud CDN',
    };
  }

  const filename = extractPdfFilename(signal.pdf_path);
  if (filename) {
    return {
      url: `/api/reports/${encodeURIComponent(filename)}`,
      source: 'proxy',
      label: 'Server PDF',
    };
  }

  return {
    url: null,
    source: 'unavailable',
    label: 'Unavailable',
  };
}

export function parseRiskReward(riskReward: number | string | undefined): string {
  if (riskReward == null) return 'N/A';
  if (typeof riskReward === 'string' && riskReward.includes(':')) {
    const parsed = Number(riskReward.split(':')[1]);
    return !Number.isNaN(parsed) ? parsed.toFixed(2) : 'N/A';
  }
  const parsed = Number(riskReward);
  return !Number.isNaN(parsed) ? parsed.toFixed(2) : 'N/A';
}

export function formatConfluenceHit(hit: string): string {
  return hit
    .replace(/^vote_/, '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
