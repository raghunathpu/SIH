import React from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
}

export const MetricsBar: React.FC<Props> = ({ state }) => {
  if (!state) return null;
  const m = state.metrics;

  const MetricItem = ({ label, value, unit = '', color = 'text-primary', glow = false }: any) => (
    <div className="flex flex-col gap-1 px-4 border-r border-white/5 last:border-0" style={{ flex: 1 }}>
      <span className="text-xs text-secondary font-medium tracking-wide uppercase">{label}</span>
      <div className={`text-2xl font-bold font-mono tracking-tight ${color}`} style={glow ? { textShadow: `0 0 10px currentColor` } : {}}>
        {value} <span className="text-sm opacity-50">{unit}</span>
      </div>
    </div>
  );

  return (
    <div className="card" style={{ padding: '1rem', display: 'flex', justifyContent: 'space-between', background: 'var(--bg-glass)' }}>
      <MetricItem label="Tick" value={state.tick} color="text-blue-400" />
      <MetricItem label="Tasks Done" value={`${m.tasks_completed}/${m.tasks_total}`} color="text-emerald-400" glow={m.tasks_completed > 0} />
      <MetricItem label="Avg Task Time" value={m.average_task_completion_time.toFixed(1)} unit="ticks" color="text-indigo-400" />
      <MetricItem label="Avg Wait Time" value={m.average_waiting_time.toFixed(1)} unit="ticks" color="text-amber-400" />
      <MetricItem label="Collisions" value={m.collisions} color={m.collisions > 0 ? 'text-rose-500' : 'text-emerald-500'} glow={m.collisions === 0} />
      <MetricItem label="Conflicts Res." value={m.conflicts_resolved} color="text-purple-400" />
      <MetricItem label="Comm Events" value={m.communication_events} color="text-slate-300" />
    </div>
  );
};
