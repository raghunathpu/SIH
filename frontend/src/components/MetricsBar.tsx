import React from 'react';
import type { SimulationState } from '../types';

export const MetricsBar: React.FC<{ state: SimulationState | null }> = ({ state }) => {
  if (!state) return null;

  const { metrics, tick } = state;

  return (
    <div className="card" style={{ padding: '1rem' }}>
      <div className="flex justify-between items-center text-sm">
        <div className="flex flex-col gap-1 text-center">
          <span className="text-tertiary">Tick</span>
          <span className="font-mono text-xl text-primary">{tick}</span>
        </div>
        
        <div style={{ width: '1px', height: '40px', background: 'var(--border-color)' }}></div>
        
        <div className="flex flex-col gap-1 text-center">
          <span className="text-tertiary">Tasks</span>
          <span className="font-mono text-xl" style={{ color: metrics.tasks_completed === metrics.tasks_total && metrics.tasks_total > 0 ? 'var(--status-success)' : 'var(--text-primary)' }}>
            {metrics.tasks_completed} / {metrics.tasks_total}
          </span>
        </div>

        <div style={{ width: '1px', height: '40px', background: 'var(--border-color)' }}></div>

        <div className="flex flex-col gap-1 text-center">
          <span className="text-tertiary">Wait Time</span>
          <span className="font-mono text-xl">{metrics.total_waiting_time}</span>
        </div>

        <div style={{ width: '1px', height: '40px', background: 'var(--border-color)' }}></div>

        <div className="flex flex-col gap-1 text-center">
          <span className="text-tertiary">Deadlocks</span>
          <span className="font-mono text-xl">{metrics.deadlocks_detected}</span>
        </div>

        <div style={{ width: '1px', height: '40px', background: 'var(--border-color)' }}></div>

        <div className="flex flex-col gap-1 text-center">
          <span className="text-tertiary">Collisions</span>
          <span className="font-mono text-xl" style={{ color: metrics.collisions > 0 ? 'var(--status-error)' : 'var(--status-success)' }}>
            {metrics.collisions}
          </span>
        </div>
      </div>
    </div>
  );
};
