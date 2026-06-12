'use client';

import { useEffect, useState } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from 'recharts';
import type { Signal } from '../types/signal';
import styles from './AnalyticsCharts.module.css';

interface AnalyticsChartsProps {
  signals: Signal[];
}

const TOOLTIP_STYLE = {
  background: 'rgba(4, 8, 20, 0.95)',
  border: '1px solid rgba(34, 211, 238, 0.2)',
  borderRadius: '10px',
  color: '#f0f4ff',
  fontSize: '0.82rem',
};

export default function AnalyticsCharts({ signals }: AnalyticsChartsProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className={styles.loading}>Calibrating orbital analytics…</div>;
  }

  const closedSignals = signals.filter((s) => s.status === 'TP_HIT' || s.status === 'SL_HIT');

  const tpCount = closedSignals.filter((s) => s.status === 'TP_HIT').length;
  const slCount = closedSignals.filter((s) => s.status === 'SL_HIT').length;

  const pieData = [
    { name: 'Take Profit', value: tpCount },
    { name: 'Stop Loss', value: slCount },
  ];

  const COLORS = ['#34d399', '#f87171'];

  const recentClosed = [...closedSignals].slice(0, 15).reverse().map((s) => {
    const pnl = s.pnl_r_multiple != null ? Number(s.pnl_r_multiple) : null;
    return {
      name: s.symbol,
      RR: pnl != null && !Number.isNaN(pnl) ? pnl : 0,
      outcome: s.status,
      fill: s.status === 'TP_HIT' ? 'url(#greenGradient)' : 'url(#redGradient)',
    };
  });

  const cumulativeR = [...closedSignals]
    .filter((s) => s.pnl_r_multiple != null && !Number.isNaN(Number(s.pnl_r_multiple)))
    .reverse()
    .reduce<{ name: string; equity: number }[]>((acc, s, idx) => {
      const prev = acc.length > 0 ? acc[acc.length - 1].equity : 0;
      acc.push({
        name: `#${idx + 1}`,
        equity: prev + Number(s.pnl_r_multiple),
      });
      return acc;
    }, [])
    .slice(-20);

  return (
    <div className={styles.grid}>
      <div className={styles.chartCard} style={{ animationDelay: '0.1s' }}>
        <h3 className={styles.title}>Win Rate Distribution</h3>
        <div className={styles.chartArea}>
          <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <defs>
                  <linearGradient id="pieGreen" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#34d399" stopOpacity={0.9}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0.6}/>
                  </linearGradient>
                  <linearGradient id="pieRed" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f87171" stopOpacity={0.9}/>
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0.6}/>
                  </linearGradient>
                </defs>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={65}
                  outerRadius={105}
                  paddingAngle={6}
                  dataKey="value"
                  stroke="rgba(255,255,255,0.05)"
                  strokeWidth={2}
                >
                  {pieData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={index === 0 ? 'url(#pieGreen)' : 'url(#pieRed)'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: '#f0f4ff' }} />
                <Legend verticalAlign="bottom" height={36} />
              </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className={styles.chartCard} style={{ animationDelay: '0.2s' }}>
        <h3 className={styles.title}>Recent Trades R-Multiple</h3>
        <div className={styles.chartArea}>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={recentClosed} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <defs>
                <linearGradient id="greenGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#34d399" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.2}/>
                </linearGradient>
                <linearGradient id="redGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f87171" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.2}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.08)" vertical={false} />
              <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ fill: 'rgba(34,211,238,0.08)' }} contentStyle={TOOLTIP_STYLE} />
              <Bar dataKey="RR" radius={[4, 4, 0, 0]}>
                {recentClosed.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {cumulativeR.length > 0 && (
        <div className={styles.chartCard} style={{ animationDelay: '0.3s' }}>
          <h3 className={styles.title}>Cumulative Net R</h3>
          <div className={styles.chartArea}>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={cumulativeR} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                <defs>
                  <linearGradient id="purpleGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#c084fc" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="#9333ea" stopOpacity={0.2}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.08)" vertical={false} />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: 'rgba(34,211,238,0.08)' }} contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="equity" fill="url(#purpleGradient)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
