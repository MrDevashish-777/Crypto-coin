import { Search } from 'lucide-react';
import styles from './FilterBar.module.css';

interface FilterBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  directionFilter: 'ALL' | 'BUY' | 'SELL';
  onDirectionChange: (dir: 'ALL' | 'BUY' | 'SELL') => void;
}

export default function FilterBar({
  searchQuery,
  onSearchChange,
  directionFilter,
  onDirectionChange,
}: FilterBarProps) {
  return (
    <div className={styles.container}>
      <div className={styles.searchWrapper}>
        <div className={styles.hudPrefix}>&gt;_</div>
        <input
          type="text"
          className={styles.input}
          placeholder="Scan sector — enter symbol (e.g. BTC)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        <Search className={styles.searchIcon} size={16} />
      </div>
      <select
        className={styles.filterSelect}
        value={directionFilter}
        onChange={(e) => onDirectionChange(e.target.value as 'ALL' | 'BUY' | 'SELL')}
      >
        <option value="ALL">All Directions</option>
        <option value="BUY">Long / Buy</option>
        <option value="SELL">Short / Sell</option>
      </select>
    </div>
  );
}
