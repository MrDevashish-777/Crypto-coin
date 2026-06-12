'use client';

import { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import type { Signal } from '../types/signal';
import {
  formatConfluenceHit,
  formatGeneratedAt,
  formatIstDate,
  getPdfDownloadInfo,
  parseRiskReward,
  toTradingViewInterval,
  toTradingViewSymbol,
} from '../lib/signalUtils';
import TradingViewChart from './TradingViewChart';
import styles from './SignalDetailModal.module.css';

interface SignalDetailModalProps {
  signal: Signal | null;
  onClose: () => void;
}

export default function SignalDetailModal({ signal, onClose }: SignalDetailModalProps) {
  useEffect(() => {
    if (!signal) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [signal, onClose]);

  if (!signal) return null;

  const isBuy = signal.direction === 'BUY';
  const generated = signal.generated_at ? formatGeneratedAt(signal.generated_at) : null;
  const pdfInfo = getPdfDownloadInfo(signal);
  const tvSymbol = toTradingViewSymbol(signal);
  const tvInterval = toTradingViewInterval(signal.timeframe);
  const isClosed = signal.status !== 'OPEN';

  return (
    <AnimatePresence>
      <motion.div
        className={styles.overlay}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      >
        <motion.div
          className={styles.modal}
          initial={{ opacity: 0, y: 30, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.97 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className={styles.modalHeader}>
            <div className={styles.titleGroup}>
              <h2>{signal.symbol}</h2>
              <div className={styles.subtitle}>
                {signal.pair || `${signal.symbol}_USDT`}
                {generated && ` · Generated ${generated.absolute} (${generated.relative})`}
              </div>
              <div className={styles.headerBadges}>
                <span className={`${styles.badge} ${isBuy ? styles.badgeBuy : styles.badgeSell}`}>
                  {signal.direction}
                </span>
                <span className={`${styles.badge} ${styles.badgeStatus}`}>{signal.status}</span>
                {signal.quality_tier && (
                  <span className={`${styles.badge} ${styles[`badgeTier${signal.quality_tier}`]}`}>
                    Tier {signal.quality_tier}
                  </span>
                )}
                {signal.timeframe && (
                  <span className={`${styles.badge} ${styles.badgeStatus}`}>{signal.timeframe}</span>
                )}
              </div>
            </div>
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>

          <div className={styles.body}>
            <div className={styles.chartSection}>
              <TradingViewChart
                key={`${signal.signal_id}-${tvSymbol}-${tvInterval}`}
                symbol={tvSymbol}
                interval={tvInterval}
              />
              <div className={styles.levelsPanel}>
                <h4>Trade Levels</h4>
                <div className={styles.levelRow}>
                  <span className={styles.levelLabel}>Entry</span>
                  <span className={`${styles.levelValue} ${styles.levelEntry}`}>
                    {signal.entry_range
                      ? `${signal.entry_range[0]} – ${signal.entry_range[1]}`
                      : '—'}
                  </span>
                </div>
                <div className={styles.levelRow}>
                  <span className={styles.levelLabel}>Target</span>
                  <span className={`${styles.levelValue} ${styles.levelTarget}`}>
                    {signal.target}
                  </span>
                </div>
                <div className={styles.levelRow}>
                  <span className={styles.levelLabel}>Stop Loss</span>
                  <span className={`${styles.levelValue} ${styles.levelStop}`}>
                    {signal.stop_loss}
                  </span>
                </div>
                <div className={styles.levelRow}>
                  <span className={styles.levelLabel}>Live Price</span>
                  <span className={styles.levelValue}>
                    {signal.live_price_at_signal ?? '—'}
                  </span>
                </div>
                <div className={styles.levelRow}>
                  <span className={styles.levelLabel}>Chart</span>
                  <span className={styles.levelValue} style={{ fontSize: '0.7rem' }}>
                    {tvSymbol}
                  </span>
                </div>
              </div>
            </div>

            <div className={styles.section}>
              <div className={styles.sectionTitle}>Trade Setup</div>
              <div className={styles.grid2}>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Timeframe</div>
                  <div className={styles.statValue}>{signal.timeframe || '—'}</div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Horizon</div>
                  <div className={styles.statValue}>{signal.trade_horizon || '—'}</div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Leverage</div>
                  <div className={styles.statValue}>{signal.leverage}x</div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Risk : Reward</div>
                  <div className={styles.statValue}>
                    {typeof signal.risk_reward === 'string'
                      ? signal.risk_reward
                      : parseRiskReward(signal.risk_reward)}
                  </div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>SL %</div>
                  <div className={styles.statValue}>
                    {signal.sl_pct != null ? `${signal.sl_pct}%` : '—'}
                  </div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>TP %</div>
                  <div className={styles.statValue}>
                    {signal.tp_pct != null ? `${signal.tp_pct}%` : '—'}
                  </div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Valid Until (IST)</div>
                  <div className={styles.statValue}>{formatIstDate(signal.valid_until_ist)}</div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Margin</div>
                  <div className={styles.statValue}>{signal.margin_currency || 'USDT'}</div>
                </div>
              </div>
            </div>

            <div className={styles.section}>
              <div className={styles.sectionTitle}>Why This Trade</div>
              {signal.reason_why_token && (
                <div className={styles.reasonBlock}>
                  <h4>Why This Token</h4>
                  <p>{signal.reason_why_token}</p>
                </div>
              )}
              {signal.reason_entry && (
                <div className={styles.reasonBlock}>
                  <h4>Entry Rationale</h4>
                  <p>{signal.reason_entry}</p>
                </div>
              )}
              {signal.reason_monitor && (
                <div className={styles.reasonBlock}>
                  <h4>What to Monitor</h4>
                  <p>{signal.reason_monitor}</p>
                </div>
              )}
            </div>

            {(signal.confluence_hits?.length || signal.indicators?.length) ? (
              <div className={styles.section}>
                <div className={styles.sectionTitle}>Confluence & Indicators</div>
                {signal.confluence_hits && signal.confluence_hits.length > 0 && (
                  <div className={styles.chips} style={{ marginBottom: '0.75rem' }}>
                    {signal.confluence_hits.map((hit) => (
                      <span key={hit} className={styles.chip}>
                        {formatConfluenceHit(hit)}
                      </span>
                    ))}
                  </div>
                )}
                {signal.indicators && signal.indicators.length > 0 && (
                  <div className={styles.chips}>
                    {signal.indicators.map((ind) => (
                      <span key={ind} className={`${styles.chip} ${styles.chipIndicator}`}>
                        {ind}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : null}

            <div className={styles.section}>
              <div className={styles.sectionTitle}>Scores</div>
              <div className={styles.grid2}>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Confidence</div>
                  <div className={styles.statValue}>
                    {Math.round((Number(signal.confidence_score) || 0) * 100)}%
                  </div>
                </div>
                <div className={styles.statBox}>
                  <div className={styles.statLabel}>Composite Score</div>
                  <div className={styles.statValue}>
                    {signal.composite_score != null
                      ? Number(signal.composite_score).toFixed(3)
                      : '—'}
                  </div>
                </div>
              </div>
            </div>

            {isClosed && (
              <div className={styles.section}>
                <div className={styles.sectionTitle}>Outcome</div>
                <div className={styles.grid2}>
                  <div className={styles.statBox}>
                    <div className={styles.statLabel}>Result</div>
                    <div className={styles.statValue}>{signal.outcome || signal.status}</div>
                  </div>
                  <div className={styles.statBox}>
                    <div className={styles.statLabel}>PnL (R-multiple)</div>
                    <div className={styles.statValue}>
                      {signal.pnl_r_multiple != null ? `${signal.pnl_r_multiple}R` : '—'}
                    </div>
                  </div>
                  <div className={styles.statBox}>
                    <div className={styles.statLabel}>Closed At</div>
                    <div className={styles.statValue}>{formatIstDate(signal.closed_at)}</div>
                  </div>
                </div>
              </div>
            )}

            <div className={styles.actions}>
              {pdfInfo.url ? (
                <>
                  <a
                    href={pdfInfo.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.downloadBtn}
                  >
                    Download PDF Report
                  </a>
                  <span className={styles.pdfSource}>Source: {pdfInfo.label}</span>
                </>
              ) : (
                <span className={styles.unavailable}>
                  PDF report unavailable — configure Cloudinary or ensure backend is reachable.
                </span>
              )}
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
