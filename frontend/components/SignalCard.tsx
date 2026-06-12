import { motion } from 'framer-motion';
import type { Signal } from '../types/signal';
import {
  formatGeneratedAt,
  getPdfDownloadInfo,
  parseRiskReward,
} from '../lib/signalUtils';
import styles from './SignalCard.module.css';

interface SignalCardProps {
  signal: Signal;
  index: number;
  onSelect?: (signal: Signal) => void;
}

export default function SignalCard({ signal, index, onSelect }: SignalCardProps) {
  const isBuy = signal.direction === 'BUY';
  const isOpen = signal.status === 'OPEN';

  const confidencePct = Math.round((Number(signal.confidence_score) || 0) * 100);
  const displayRR = parseRiskReward(signal.risk_reward);
  const pdfInfo = getPdfDownloadInfo(signal);
  const generated = signal.generated_at ? formatGeneratedAt(signal.generated_at) : null;

  const handleCardClick = () => {
    onSelect?.(signal);
  };

  const handleDownloadClick = (e: React.MouseEvent) => {
    e.stopPropagation();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        type: 'spring',
        stiffness: 260,
        damping: 20,
        delay: index * 0.05,
      }}
      whileHover={{ y: -5, scale: 1.02 }}
      className={`${styles.card} ${isBuy ? styles.buy : styles.sell} ${onSelect ? styles.clickable : ''}`}
      onClick={handleCardClick}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect(signal);
              }
            }
          : undefined
      }
    >
      <div className={styles.header}>
        <div className={styles.symbolGroup}>
          <div>
            <div className={styles.symbolRow}>
              <div className={styles.symbol}>{signal.symbol}</div>
              {isOpen && <div className={styles.livePulse} title="Live Signal" />}
            </div>
            {generated && (
              <div className={styles.generatedAt} title={generated.absolute}>
                {generated.relative} · {generated.absolute}
              </div>
            )}
          </div>
        </div>
        <div className={styles.badges}>
          {signal.quality_tier && (
            <span className={`${styles.tier} ${styles[`tier${signal.quality_tier}`]}`}>
              Tier {signal.quality_tier}
            </span>
          )}
          <div className={styles.status}>{signal.status}</div>
          <div className={`${styles.direction} ${isBuy ? styles.buy : styles.sell}`}>
            {signal.direction}
          </div>
        </div>
      </div>

      <div className={styles.trajectoryContainer}>
        <div className={styles.trajectoryTop}>
          <span className={styles.trajLeverage}>Lev: {signal.leverage}x</span>
          <span className={styles.trajRR}>RR: {displayRR}</span>
        </div>
        
        <div className={styles.trajectoryBar}>
          <div className={styles.trajPoint}>
            <span className={styles.trajLabel}>SL</span>
            <span className={`${styles.trajValue} ${styles.stop}`}>{signal.stop_loss}</span>
          </div>
          <div className={`${styles.trajLine} ${isBuy ? styles.trajLineBuy : styles.trajLineSell}`} />
          <div className={styles.trajPoint}>
            <span className={styles.trajLabel}>Entry</span>
            <span className={styles.trajValue}>
              {signal.entry_range ? `${signal.entry_range[0]}` : 'N/A'}
            </span>
          </div>
          <div className={`${styles.trajLine} ${isBuy ? styles.trajLineBuy : styles.trajLineSell}`} />
          <div className={styles.trajPoint}>
            <span className={styles.trajLabel}>TP</span>
            <span className={`${styles.trajValue} ${styles.target}`}>{signal.target}</span>
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <div className={styles.confidence}>
          <span>Conf {confidencePct}%</span>
          <div className={styles.confidenceBar}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${confidencePct}%` }}
              transition={{ delay: 0.3 + index * 0.05, duration: 0.8, ease: 'easeOut' }}
              className={styles.confidenceFill}
            />
          </div>
        </div>
      </div>

      {onSelect && (
        <div className={styles.viewDetails}>Open mission briefing →</div>
      )}

      {pdfInfo.url && (
        <a
          href={pdfInfo.url}
          target="_blank"
          rel="noopener noreferrer"
          className={styles.downloadBtn}
          onClick={handleDownloadClick}
        >
          Download PDF Report
        </a>
      )}
    </motion.div>
  );
}
