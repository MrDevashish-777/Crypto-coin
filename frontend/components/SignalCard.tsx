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
  risk_reward: number;
  generated_at: string;
  cloudinary_pdf_url?: string;
}

export default function SignalCard({ signal, index }: { signal: Signal; index: number }) {
  const isBuy = signal.direction === 'BUY';
  const entryAvg = signal.entry_range ? (signal.entry_range[0] + signal.entry_range[1]) / 2 : 0;
  
  // Format percentage for confidence bar
  const confidencePct = Math.round((Number(signal.confidence_score) || 0) * 100);

  const parsedRR = Number(signal.risk_reward);
  const displayRR = !isNaN(parsedRR) && signal.risk_reward != null ? parsedRR.toFixed(2) : 'N/A';

  // Stagger animation based on index
  const animationDelay = `${index * 0.05}s`;

  return (
    <div 
      className={`${styles.card} ${isBuy ? styles.buy : styles.sell}`}
      style={{ animationDelay }}
    >
      <div className={styles.header}>
        <div className={styles.symbol}>{signal.symbol}</div>
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
            <div 
              className={styles.confidenceFill} 
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      </div>
      
      {signal.cloudinary_pdf_url && (
        <a 
          href={signal.cloudinary_pdf_url} 
          target="_blank" 
          rel="noopener noreferrer"
          className={styles.downloadBtn}
        >
          Download PDF Report
        </a>
      )}
    </div>
  );
}
