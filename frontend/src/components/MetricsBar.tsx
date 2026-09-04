import React from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
}

export const MetricsBar: React.FC<Props> = ({ state }) => {
  if (!state) return null;
  const m = state.metrics;

  // Count robots with active collision warnings
  const robots = Object.values(state.robots);
  const criticalCount = robots.filter(r => r.collision_risk === 'CRITICAL').length;
  const warningCount  = robots.filter(r => r.collision_risk === 'WARNING').length;
  const threatCount = criticalCount + warningCount;
  const threatColor = criticalCount > 0 ? '#ef4444' : warningCount > 0 ? '#f59e0b' : '#34d399';

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
      {/* Predictive collision threats from collision_predictor.py */}
      <div className="metric-item" style={threatCount > 0 ? { boxShadow: `inset 0 0 12px ${threatColor}22` } : {}}>
        <span className="metric-label">⚠ Pred. Threats</span>
        <div className="metric-value" style={{ color: threatColor, display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          {threatCount}
          {criticalCount > 0 && (
            <span style={{ fontSize: '0.6rem', background: '#ef444422', color: '#ef4444', border: '1px solid #ef444444', borderRadius: 4, padding: '1px 4px' }}>
              {criticalCount} CRIT
            </span>
          )}
        </div>
      </div>
      <MetricItem label="Conflicts" value={m.conflicts_resolved} color="#c084fc" />
      <MetricItem label="Comm" value={m.communication_events} color="#94a3b8" />
    </div>
  );
};
