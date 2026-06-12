import { Trophy, TrendingUp, TrendingDown, Target, DollarSign, BarChart3 } from 'lucide-react';
import styles from './StatsOverview.module.css';
import type { Signal } from '../types/signal';

interface StatsOverviewProps {
  signals: Signal[];
}

function closedWithPnl(signals: Signal[]) {
  return signals.filter(
    (s) =>
      (s.status === 'TP_HIT' || s.status === 'SL_HIT' || s.status === 'CLOSED') &&
      s.pnl_r_multiple != null &&
      !Number.isNaN(Number(s.pnl_r_multiple))
  );
}

export default function StatsOverview({ signals }: StatsOverviewProps) {
  const closedSignals = signals.filter(
    (s) => s.status === 'TP_HIT' || s.status === 'SL_HIT' || s.status === 'CLOSED'
  );

  const totalClosed = closedSignals.length;
  const tpCount = closedSignals.filter((s) => s.status === 'TP_HIT').length;
  const slCount = closedSignals.filter((s) => s.status === 'SL_HIT').length;

  const winRate = totalClosed > 0 ? ((tpCount / totalClosed) * 100).toFixed(1) : '0.0';

  const pnlSignals = closedWithPnl(signals);
  const rValues = pnlSignals.map((s) => Number(s.pnl_r_multiple));
  const netR = rValues.reduce((sum, r) => sum + r, 0);
  const expectancy = rValues.length > 0 ? netR / rValues.length : 0;
  const grossWin = rValues.filter((r) => r > 0).reduce((sum, r) => sum + r, 0);
  const grossLoss = Math.abs(rValues.filter((r) => r < 0).reduce((sum, r) => sum + r, 0));
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? grossWin : 0;

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

      <div className={styles.statCard} style={{ animationDelay: '0.4s' }}>
        <div className={`${styles.iconWrapper} ${styles.green}`}>
          <DollarSign size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Net R</span>
          <span className={styles.value}>
            {rValues.length > 0 ? `${netR >= 0 ? '+' : ''}${netR.toFixed(2)}R` : 'N/A'}
          </span>
        </div>
      </div>

      <div className={styles.statCard} style={{ animationDelay: '0.5s' }}>
        <div className={`${styles.iconWrapper} ${styles.blue}`}>
          <BarChart3 size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Expectancy</span>
          <span className={styles.value}>
            {rValues.length > 0 ? `${expectancy >= 0 ? '+' : ''}${expectancy.toFixed(2)}R` : 'N/A'}
          </span>
        </div>
      </div>

      <div className={styles.statCard} style={{ animationDelay: '0.6s' }}>
        <div className={`${styles.iconWrapper} ${styles.purple}`}>
          <Trophy size={24} />
        </div>
        <div className={styles.content}>
          <span className={styles.label}>Profit Factor</span>
          <span className={styles.value}>
            {rValues.length > 0 ? profitFactor.toFixed(2) : 'N/A'}
          </span>
        </div>
      </div>
    </div>
  );
}
