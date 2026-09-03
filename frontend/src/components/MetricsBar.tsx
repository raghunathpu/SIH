import React from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
}

export const MetricsBar: React.FC<Props> = ({ state }) => {
  if (!state) return null;
  const m = state.metrics;

  const MetricItem = ({ label, value, unit = '', color = '' }: { label: string; value: string | number; unit?: string; color?: string }) => (
    <div className="metric-item">
      <span className="metric-label">{label}</span>
      <div className="metric-value" style={{ color: color || 'var(--text-primary)' }}>
        {value}{unit && <span className="metric-unit">{unit}</span>}
      </div>
    </div>
  );

  return (
    <div className="metrics-bar">
      <MetricItem label="Tick" value={state.tick} color="#60a5fa" />
      <MetricItem label="Tasks Done" value={`${m.tasks_completed}/${m.tasks_total}`} color="#34d399" />
      <MetricItem label="Avg Task" value={m.average_task_completion_time.toFixed(1)} unit="t" color="#818cf8" />
      <MetricItem label="Avg Wait" value={m.average_waiting_time.toFixed(1)} unit="t" color="#fbbf24" />
      <MetricItem label="Collisions" value={m.collisions} color={m.collisions > 0 ? '#f87171' : '#34d399'} />
      <MetricItem label="Conflicts" value={m.conflicts_resolved} color="#c084fc" />
      <MetricItem label="Comm" value={m.communication_events} color="#94a3b8" />
    </div>
  );
};
