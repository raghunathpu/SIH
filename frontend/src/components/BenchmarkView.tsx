import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from 'recharts';
import type { BenchmarkComparison } from '../types';

interface Props {
  result: BenchmarkComparison;
  onClose: () => void;
}

export const BenchmarkView: React.FC<Props> = ({ result, onClose }) => {
  const { baseline, distributed, improvement_pct, collision_distributed } = result;

  // Chart data formatting
  const chartData = [
    {
      name: 'Avg Task Time',
      Baseline: baseline?.avg_completion_time || 0,
      Distributed: distributed?.avg_completion_time || 0,
    },
    {
      name: 'Total Time',
      Baseline: baseline?.total_completion_time || 0,
      Distributed: distributed?.total_completion_time || 0,
    },
    {
      name: 'Wait Time',
      Baseline: baseline?.total_waiting_time || 0,
      Distributed: distributed?.total_waiting_time || 0,
    }
  ];

  const success = improvement_pct >= 20 && collision_distributed === 0;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '800px', background: 'var(--bg-base)', border: '1px solid rgba(255,255,255,0.1)', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.8)' }}>
        
        <div className="modal-header border-b border-white/5 relative overflow-hidden" style={{ background: 'var(--bg-surface)' }}>
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-emerald-500/10 z-0"></div>
          <div className="relative z-10 flex justify-between items-center w-full">
            <div>
              <h2 className="text-2xl font-bold font-display tracking-tight text-white">Performance Benchmark</h2>
              <div className="text-sm text-secondary font-mono mt-1">Scenario: {result.scenario_id}</div>
            </div>
            <button className="close-btn" onClick={onClose}>✕</button>
          </div>
        </div>

        <div className="modal-body p-6 flex flex-col gap-6" style={{ background: 'var(--bg-base)' }}>
          
          {/* Big Result Badge */}
          <div className={`p-6 rounded-xl border ${success ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-blue-500/10 border-blue-500/30'} flex flex-col items-center justify-center text-center relative overflow-hidden`}>
            {success && <div className="absolute inset-0 bg-gradient-to-r from-emerald-500/5 to-teal-500/5 pointer-events-none"></div>}
            
            <div className="text-secondary text-sm font-semibold tracking-widest uppercase mb-2">Efficiency Improvement</div>
            <div className={`text-6xl font-black font-display tracking-tighter ${success ? 'text-emerald-400 text-shadow-glow' : 'text-blue-400'}`}>
              {improvement_pct.toFixed(1)}%
            </div>
            
            {success ? (
              <div className="mt-4 inline-flex items-center gap-2 bg-emerald-500/20 text-emerald-300 px-4 py-1.5 rounded-full text-sm font-bold border border-emerald-500/30">
                <span>🏆 SUCCESS CRITERIA MET</span>
              </div>
            ) : (
              <div className="mt-4 inline-flex items-center gap-2 bg-amber-500/20 text-amber-300 px-4 py-1.5 rounded-full text-sm font-bold border border-amber-500/30">
                <span>⚠️ TARGET: 20%</span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-6">
            {/* Chart */}
            <div className="bg-surface-elevated rounded-lg p-4 border border-white/5" style={{ height: '300px' }}>
              <h3 className="text-sm font-semibold text-secondary uppercase tracking-widest mb-4">Metric Comparison</h3>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 5, right: 0, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="#a0a6b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#a0a6b8" fontSize={12} tickLine={false} axisLine={false} />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: '#1c1f26', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Legend wrapperStyle={{ paddingTop: '20px' }} />
                  <Bar dataKey="Baseline" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Distributed" fill="#10b981" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Stats Table */}
            <div className="bg-surface-elevated rounded-lg border border-white/5 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 bg-white/5">
                    <th className="text-left p-3 text-secondary font-medium">Metric</th>
                    <th className="text-right p-3 text-amber-400 font-medium">Baseline</th>
                    <th className="text-right p-3 text-emerald-400 font-medium">Distributed</th>
                  </tr>
                </thead>
                <tbody className="font-mono">
                  <tr className="border-b border-white/5">
                    <td className="p-3 text-primary">Avg Task Time</td>
                    <td className="p-3 text-right text-amber-200">{baseline?.avg_completion_time.toFixed(1)}</td>
                    <td className="p-3 text-right text-emerald-200">{distributed?.avg_completion_time.toFixed(1)}</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="p-3 text-primary">Collisions</td>
                    <td className="p-3 text-right text-amber-200">{baseline?.collisions}</td>
                    <td className="p-3 text-right text-emerald-200">{distributed?.collisions}</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="p-3 text-primary">Deadlocks Res.</td>
                    <td className="p-3 text-right text-amber-200">-</td>
                    <td className="p-3 text-right text-emerald-200">{distributed?.deadlock_recoveries}</td>
                  </tr>
                  <tr className="border-b border-white/5">
                    <td className="p-3 text-primary">P2P Comm Events</td>
                    <td className="p-3 text-right text-amber-200">0 (Central)</td>
                    <td className="p-3 text-right text-emerald-200">{distributed?.communication_events}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
