import { motion } from 'framer-motion';
import styles from './SignalCard.module.css';

export interface Signal {
  _id: string;
  signal_id: string;
  symbol: string;
  direction: 'BUY' | 'SELL';
  status: string;
  entry_range: number[];
  target: number;
  stop_loss: number;
  confidence_score: number;
  leverage: number;
  risk_reward: number | string;
  generated_at: string;
  cloudinary_pdf_url?: string;
  pdf_path?: string;
}

export default function SignalCard({ signal, index }: { signal: Signal; index: number }) {
  const isBuy = signal.direction === 'BUY';
  const isOpen = signal.status === 'OPEN';
  
  // Format percentage for confidence bar
  const confidencePct = Math.round((Number(signal.confidence_score) || 0) * 100);

  let parsedRR = 0;
  if (typeof signal.risk_reward === 'string' && signal.risk_reward.includes(':')) {
    parsedRR = Number(signal.risk_reward.split(':')[1]);
  } else {
    parsedRR = Number(signal.risk_reward);
  }
  const displayRR = !isNaN(parsedRR) && signal.risk_reward != null ? parsedRR.toFixed(2) : 'N/A';

  let downloadUrl = signal.cloudinary_pdf_url;
  if (!downloadUrl && signal.pdf_path) {
    const filename = signal.pdf_path.split('/').pop() || signal.pdf_path.split('\\').pop();
    if (filename) {
      downloadUrl = `http://localhost:8003/api/v1/advisor/reports/${filename}`;
    }
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ 
        type: 'spring', 
        stiffness: 260, 
        damping: 20, 
        delay: index * 0.05 
      }}
      whileHover={{ y: -5, scale: 1.02 }}
      className={`${styles.card} ${isBuy ? styles.buy : styles.sell}`}
    >
      <div className={styles.header}>
        <div className={styles.symbolGroup}>
          <div className={styles.symbol}>{signal.symbol}</div>
          {isOpen && <div className={styles.livePulse} title="Live Signal" />}
        </div>
        <div className={styles.status}>{signal.status}</div>
        <div className={`${styles.direction} ${isBuy ? styles.buy : styles.sell}`}>
          {signal.direction}
        </div>
      </div>

      <div className={styles.row}>
        <span className={styles.label}>Entry</span>
        <span className={styles.value}>
          {signal.entry_range ? `${signal.entry_range[0]} - ${signal.entry_range[1]}` : 'N/A'}
        </span>
      </div>

      <div className={styles.row}>
        <span className={styles.label}>Target</span>
        <span className={`${styles.value} ${styles.target}`}>{signal.target}</span>
      </div>

      <div className={styles.row}>
        <span className={styles.label}>Stop Loss</span>
        <span className={`${styles.value} ${styles.stop}`}>{signal.stop_loss}</span>
      </div>

      <div className={styles.row}>
        <span className={styles.label}>Leverage</span>
        <span className={styles.value}>{signal.leverage}x</span>
      </div>

      <div className={styles.footer}>
        <span>RR: {displayRR}</span>
        <div className={styles.confidence}>
          <span>Conf {confidencePct}%</span>
          <div className={styles.confidenceBar}>
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${confidencePct}%` }}
              transition={{ delay: 0.3 + (index * 0.05), duration: 0.8, ease: "easeOut" }}
              className={styles.confidenceFill} 
            />
          </div>
        </div>
      </div>
      
      {downloadUrl && (
        <a 
          href={downloadUrl} 
          target="_blank" 
          rel="noopener noreferrer"
          className={styles.downloadBtn}
        >
          Download PDF Report
        </a>
      )}
    </motion.div>
  );
}
