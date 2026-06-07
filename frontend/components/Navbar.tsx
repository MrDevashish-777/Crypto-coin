import { Activity, CheckCircle, BarChart2 } from 'lucide-react';
import styles from './Navbar.module.css';

export type TabType = 'OPEN' | 'CLOSED' | 'ANALYTICS';

interface NavbarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

export default function Navbar({ activeTab, onTabChange }: NavbarProps) {
  return (
    <nav className={styles.navbar}>
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'OPEN' ? styles.active : ''}`}
          onClick={() => onTabChange('OPEN')}
        >
          <Activity className={styles.icon} />
          Open Signals
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'CLOSED' ? styles.active : ''}`}
          onClick={() => onTabChange('CLOSED')}
        >
          <CheckCircle className={styles.icon} />
          Closed Signals
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'ANALYTICS' ? styles.active : ''}`}
          onClick={() => onTabChange('ANALYTICS')}
        >
          <BarChart2 className={styles.icon} />
          Analytics
        </button>
      </div>
    </nav>
  );
}
