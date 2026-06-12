'use client';

import { useEffect, useRef, useState } from 'react';
import styles from './SignalDetailModal.module.css';

const CHART_HEIGHT = 420;

interface TradingViewChartProps {
  symbol: string;
  interval: string;
}

export default function TradingViewChart({ symbol, interval }: TradingViewChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    setStatus('loading');
    container.innerHTML = '';

    let cancelled = false;

    const initWidget = () => {
      if (cancelled || !containerRef.current) return;

      const wrapper = document.createElement('div');
      wrapper.className = 'tradingview-widget-container';
      wrapper.style.height = `${CHART_HEIGHT}px`;
      wrapper.style.width = '100%';

      const widgetEl = document.createElement('div');
      widgetEl.className = 'tradingview-widget-container__widget';
      widgetEl.style.height = '100%';
      widgetEl.style.width = '100%';

      const script = document.createElement('script');
      script.type = 'text/javascript';
      script.async = true;
      script.src =
        'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
      script.textContent = JSON.stringify({
        autosize: false,
        width: '100%',
        height: CHART_HEIGHT,
        symbol,
        interval,
        timezone: 'Asia/Kolkata',
        theme: 'dark',
        style: '1',
        locale: 'en',
        enable_publishing: false,
        allow_symbol_change: false,
        hide_side_toolbar: false,
        withdateranges: true,
        save_image: false,
        calendar: false,
        support_host: 'https://www.tradingview.com',
      });

      script.onload = () => {
        if (!cancelled) setStatus('ready');
      };
      script.onerror = () => {
        if (!cancelled) setStatus('error');
      };

      wrapper.appendChild(widgetEl);
      wrapper.appendChild(script);
      container.appendChild(wrapper);

      // TradingView script may not fire onload; mark ready after brief delay
      const readyTimer = window.setTimeout(() => {
        if (!cancelled) setStatus('ready');
      }, 2500);

      return () => window.clearTimeout(readyTimer);
    };

    // Wait for modal layout to settle before injecting the widget
    const layoutTimer = window.setTimeout(() => {
      requestAnimationFrame(initWidget);
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(layoutTimer);
      container.innerHTML = '';
    };
  }, [symbol, interval]);

  return (
    <div className={styles.chartWrapper}>
      {status === 'loading' && (
        <div className={styles.chartLoading}>Loading chart for {symbol}…</div>
      )}
      {status === 'error' && (
        <div className={styles.chartError}>
          Chart failed to load.{' '}
          <a
            href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(symbol)}&interval=${interval}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open in TradingView
          </a>
        </div>
      )}
      <div
        ref={containerRef}
        className={styles.chartContainer}
        style={{ height: CHART_HEIGHT, minHeight: CHART_HEIGHT }}
      />
    </div>
  );
}
