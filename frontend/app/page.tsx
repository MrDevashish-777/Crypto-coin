'use client';

import { useEffect, useState } from 'react';
import SignalCard, { Signal } from '../components/SignalCard';
import Navbar, { TabType } from '../components/Navbar';
import StatsOverview from '../components/StatsOverview';
import AnalyticsCharts from '../components/AnalyticsCharts';
import styles from '../components/SignalCard.module.css';

export default function Home() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('OPEN');

  const fetchSignals = async () => {
    try {
      const res = await fetch('/api/signals');
      if (!res.ok) throw new Error('Failed to fetch signals');
      const data = await res.json();
      setSignals(data.signals || []);
      setLastUpdated(new Date());
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSignals();

    // Auto-refresh every 30 seconds
    const intervalId = setInterval(() => {
      fetchSignals();
    }, 30000);

    return () => clearInterval(intervalId);
  }, []);

  // Filter signals based on active tab
  const openSignals = signals.filter(s => s.status === 'OPEN');
  const closedSignals = signals.filter(s => s.status === 'TP_HIT' || s.status === 'SL_HIT' || s.status === 'CLOSED');

  return (
    <div className="container">
      <header className="header">
        <h1>Crypto Signals</h1>
        <p>Professional AI-driven trading analytics</p>
        <p style={{ fontSize: '0.8rem', marginTop: '10px', color: 'var(--text-secondary)' }}>
          Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : '...'}
        </p>
      </header>

      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      {error && (
        <div style={{ color: 'var(--danger)', textAlign: 'center', marginBottom: '2rem' }}>
          {error}
        </div>
      )}

      {loading && signals.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
          Loading dashboard...
        </div>
      ) : (
        <div style={{ animation: 'fadeInDown 0.4s ease-out' }} key={activeTab}>
          
          {activeTab === 'ANALYTICS' && (
            <>
              <StatsOverview signals={signals} />
              <AnalyticsCharts signals={signals} />
            </>
          )}

          {activeTab === 'OPEN' && (
            <div className={styles.grid}>
              {openSignals.length === 0 ? (
                <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No open signals found.
                </div>
              ) : (
                openSignals.map((signal, idx) => (
                  <SignalCard key={signal._id || signal.signal_id} signal={signal} index={idx} />
                ))
              )}
            </div>
          )}

          {activeTab === 'CLOSED' && (
            <div className={styles.grid}>
              {closedSignals.length === 0 ? (
                <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No closed signals found.
                </div>
              ) : (
                closedSignals.map((signal, idx) => (
                  <SignalCard key={signal._id || signal.signal_id} signal={signal} index={idx} />
                ))
              )}
            </div>
          )}

        </div>
      )}
    </div>
  );
}
