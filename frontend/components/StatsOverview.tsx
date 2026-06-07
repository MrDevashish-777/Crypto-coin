import { Trophy, TrendingUp, TrendingDown, Target } from 'lucide-react';
import styles from './StatsOverview.module.css';
import type { Signal } from './SignalCard';

interface StatsOverviewProps {
  signals: Signal[];
}

export default function StatsOverview({ signals }: StatsOverviewProps) {
  const closedSignals = signals.filter(s => s.status === 'TP_HIT' || s.status === 'SL_HIT' || s.status === 'CLOSED');
  
  const totalClosed = closedSignals.length;
  const tpCount = closedSignals.filter(s => s.status === 'TP_HIT').length;
  const slCount = closedSignals.filter(s => s.status === 'SL_HIT').length;
  
  const winRate = totalClosed > 0 ? ((tpCount / totalClosed) * 100).toFixed(1) : '0.0';

  return (
    <div className={styles.grid}>
      <div className={styles.statCard} style={{ animationDelay: '0s' }}>
        <div className={`${styles.iconWrapper} ${styles.blue}`}>
          <Target size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Total Closed</span>
          <span className={styles.value}>{totalClosed}</span>
        </div>
      </div>

      <div className={styles.statCard} style={{ animationDelay: '0.1s' }}>
        <div className={`${styles.iconWrapper} ${styles.green}`}>
          <TrendingUp size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Take Profits</span>
          <span className={styles.value}>{tpCount}</span>
        </div>
      </div>

      <div className={styles.statCard} style={{ animationDelay: '0.2s' }}>
        <div className={`${styles.iconWrapper} ${styles.red}`}>
          <TrendingDown size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Stop Losses</span>
          <span className={styles.value}>{slCount}</span>
        </div>
      </div>

      <div className={styles.statCard} style={{ animationDelay: '0.3s' }}>
        <div className={`${styles.iconWrapper} ${styles.purple}`}>
          <Trophy size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Win Rate</span>
          <span className={styles.value}>{winRate}%</span>
        </div>
      </div>
    </div>
  );
}
