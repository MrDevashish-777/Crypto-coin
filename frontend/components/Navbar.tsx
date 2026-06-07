import { Activity, CheckCircle, BarChart2 } from 'lucide-react';
import { motion } from 'framer-motion';
import styles from './Navbar.module.css';

export type TabType = 'OPEN' | 'CLOSED' | 'ANALYTICS';

interface NavbarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

const TABS = [
  { id: 'OPEN', label: 'Open Signals', icon: Activity },
  { id: 'CLOSED', label: 'Closed Signals', icon: CheckCircle },
  { id: 'ANALYTICS', label: 'Analytics', icon: BarChart2 },
] as const;

export default function Navbar({ activeTab, onTabChange }: NavbarProps) {
  return (
    <nav className={styles.navbar}>
      <div className={styles.tabs}>
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              className={`${styles.tab} ${isActive ? styles.active : ''}`}
              onClick={() => onTabChange(tab.id)}
            >
              {isActive && (
                <motion.div
                  layoutId="active-pill"
                  className={styles.activePill}
                  transition={{ type: "spring", stiffness: 350, damping: 30 }}
                />
              )}
              <Icon className={styles.icon} />
              {tab.label}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
