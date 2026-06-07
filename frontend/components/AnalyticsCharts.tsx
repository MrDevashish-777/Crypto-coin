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
  Legend
} from 'recharts';
import type { Signal } from './SignalCard';

interface AnalyticsChartsProps {
  signals: Signal[];
}

export default function AnalyticsCharts({ signals }: AnalyticsChartsProps) {
  const closedSignals = signals.filter(s => s.status === 'TP_HIT' || s.status === 'SL_HIT');
  
  const tpCount = closedSignals.filter(s => s.status === 'TP_HIT').length;
  const slCount = closedSignals.filter(s => s.status === 'SL_HIT').length;

  const pieData = [
    { name: 'Take Profit', value: tpCount },
    { name: 'Stop Loss', value: slCount },
  ];

  const COLORS = ['#10b981', '#ef4444'];

  // Calculate Risk/Reward distribution for the last 15 closed trades
  const recentClosed = [...closedSignals].slice(0, 15).reverse().map((s, idx) => {
    return {
      name: s.symbol,
      RR: !isNaN(Number(s.risk_reward)) ? Number(s.risk_reward) : 0,
      outcome: s.status,
      fill: s.status === 'TP_HIT' ? '#10b981' : '#ef4444'
    };
  });

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem', marginBottom: '2rem' }}>
      
      {/* Win Rate Pie Chart */}
      <div style={{ background: 'var(--glass-bg)', padding: '2rem', borderRadius: '16px', border: '1px solid var(--glass-border)', boxShadow: 'var(--glass-shadow)', animation: 'slideUp 0.6s ease-out backwards' }}>
        <h3 style={{ textAlign: 'center', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Win Rate Distribution</h3>
        <div style={{ width: '100%', height: 300 }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                paddingAngle={5}
                dataKey="value"
                stroke="none"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
                itemStyle={{ color: '#fff' }}
              />
              <Legend verticalAlign="bottom" height={36} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* RR Bar Chart */}
      <div style={{ background: 'var(--glass-bg)', padding: '2rem', borderRadius: '16px', border: '1px solid var(--glass-border)', boxShadow: 'var(--glass-shadow)', animation: 'slideUp 0.7s ease-out backwards' }}>
        <h3 style={{ textAlign: 'center', marginBottom: '1rem', color: 'var(--text-secondary)' }}>Recent Trades R:R</h3>
        <div style={{ width: '100%', height: 300 }}>
          <ResponsiveContainer>
            <BarChart data={recentClosed} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="var(--text-secondary)" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip 
                cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                contentStyle={{ background: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', color: '#fff' }}
              />
              <Bar dataKey="RR" radius={[4, 4, 0, 0]}>
                {recentClosed.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
}
