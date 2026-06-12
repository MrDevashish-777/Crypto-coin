'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import SignalCard from '../components/SignalCard';
import SignalDetailModal from '../components/SignalDetailModal';
import Navbar, { TabType } from '../components/Navbar';
import FilterBar from '../components/FilterBar';
import StatsOverview from '../components/StatsOverview';
import AnalyticsCharts from '../components/AnalyticsCharts';
import { HeroSpline } from '../components/HeroSpline';
import type { Signal } from '../types/signal';
import styles from '../components/SignalCard.module.css';

export default function Home() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('OPEN');
  const [searchQuery, setSearchQuery] = useState('');
  const [directionFilter, setDirectionFilter] = useState<'ALL' | 'BUY' | 'SELL'>('ALL');
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  const fetchSignals = async () => {
    try {
      const res = await fetch('/api/signals');
      if (!res.ok) throw new Error('Failed to fetch signals');
      const data = await res.json();
      setSignals(data.signals || []);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line
    fetchSignals();

    const intervalId = setInterval(() => {
      fetchSignals();
    }, 30000);

    return () => clearInterval(intervalId);
  }, []);

  const filteredSignals = signals.filter((s) => {
    const matchesSearch = s.symbol.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDirection = directionFilter === 'ALL' || s.direction === directionFilter;
    return matchesSearch && matchesDirection;
  });

  const openSignals = filteredSignals.filter((s) => s.status === 'OPEN');
  const closedSignals = filteredSignals.filter(
    (s) =>
      s.status === 'TP_HIT' ||
      s.status === 'SL_HIT' ||
      s.status === 'CLOSED' ||
      s.status === 'EXPIRED'
  );

  return (
    <div className="container">
      <HeroSpline />

      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      {(activeTab === 'OPEN' || activeTab === 'CLOSED') && (
        <FilterBar
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          directionFilter={directionFilter}
          onDirectionChange={setDirectionFilter}
        />
      )}

      {error && <div className="errorBanner">{error}</div>}

      {loading && signals.length === 0 ? (
        <div className="loadingState">Scanning the signal universe…</div>
      ) : (
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            style={{ width: '100%' }}
          >
            {activeTab === 'ANALYTICS' && (
              <>
                <StatsOverview signals={signals} />
                <AnalyticsCharts signals={signals} />
              </>
            )}

            {activeTab === 'OPEN' && (
              <div className={styles.grid}>
                {openSignals.length === 0 ? (
                  <div className="emptyState">No active signals in this sector of the market.</div>
                ) : (
                  openSignals.map((signal, idx) => (
                    <SignalCard
                      key={signal._id || signal.signal_id}
                      signal={signal}
                      index={idx}
                      onSelect={setSelectedSignal}
                    />
                  ))
                )}
              </div>
            )}

            {activeTab === 'CLOSED' && (
              <div className={styles.grid}>
                {closedSignals.length === 0 ? (
                  <div className="emptyState">No completed missions logged yet.</div>
                ) : (
                  closedSignals.map((signal, idx) => (
                    <SignalCard
                      key={signal._id || signal.signal_id}
                      signal={signal}
                      index={idx}
                      onSelect={setSelectedSignal}
                    />
                  ))
                )}
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      )}

      <SignalDetailModal signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
    </div>
  );
}
