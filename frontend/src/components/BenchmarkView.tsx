import React from 'react';
import type { BenchmarkComparison } from '../types';

export const BenchmarkView: React.FC<{ result: BenchmarkComparison | null, onClose: () => void }> = ({ result, onClose }) => {
  if (!result) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Benchmark Results: {result.scenario_id}</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="modal-body flex-col gap-4">
          <p className="text-secondary">
            Comparison between Baseline (Stop-and-Wait) and Distributed (Agent-based) modes.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="card p-4">
              <h3 className="mb-2 text-primary" style={{ marginBottom: '1rem' }}>Baseline Mode</h3>
              <ul className="flex-col gap-2 text-sm text-secondary" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none' }}>
                <li>Tasks Completed: <span className="font-mono text-primary">{result.baseline?.tasks_completed} / {result.baseline?.tasks_total}</span></li>
                <li>Total Completion Time: <span className="font-mono text-primary">{result.baseline?.total_completion_time}</span></li>
                <li>Total Waiting Time: <span className="font-mono text-primary">{result.baseline?.total_waiting_time}</span></li>
                <li>Deadlocks: <span className="font-mono text-primary">{result.baseline?.deadlocks}</span></li>
                <li>Collisions: <span className="font-mono text-primary">{result.baseline?.collisions}</span></li>
              </ul>
            </div>

            <div className="card p-4">
              <h3 className="mb-2 text-primary" style={{ marginBottom: '1rem' }}>Distributed Mode</h3>
              <ul className="flex-col gap-2 text-sm text-secondary" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', listStyle: 'none' }}>
                <li>Tasks Completed: <span className="font-mono text-primary">{result.distributed?.tasks_completed} / {result.distributed?.tasks_total}</span></li>
                <li>Total Completion Time: <span className="font-mono text-primary">{result.distributed?.total_completion_time}</span></li>
                <li>Total Waiting Time: <span className="font-mono text-primary">{result.distributed?.total_waiting_time}</span></li>
                <li>Reroutes (Deadlock Recoveries): <span className="font-mono text-primary">{result.distributed?.reroutes}</span></li>
                <li>Collisions: <span className="font-mono text-primary">{result.distributed?.collisions}</span></li>
              </ul>
            </div>
          </div>

          <div className="card p-4 mt-4" style={{ marginTop: '1rem' }}>
            <h3 className="mb-2 text-accent" style={{ marginBottom: '1rem' }}>Overall Improvement</h3>
            
            <div className="flex justify-between items-center bg-surface-elevated p-4 rounded" style={{ padding: '1rem', background: 'var(--bg-surface-elevated)', borderRadius: 'var(--radius-md)' }}>
              <div className="flex-col gap-1 text-center flex-1">
                <span className="text-tertiary text-sm">Completion Time Improvement</span>
                <span className="font-display text-2xl font-bold" style={{ color: result.improvement_pct > 0 ? 'var(--status-success)' : 'var(--status-warning)' }}>
                  {result.improvement_pct.toFixed(1)}%
                </span>
                <span className="text-xs text-secondary">Target: &gt;= 20%</span>
              </div>
              
              <div style={{ width: '1px', height: '60px', background: 'var(--border-color)' }}></div>
              
              <div className="flex-col gap-1 text-center flex-1">
                <span className="text-tertiary text-sm">Collisions</span>
                <span className="font-display text-2xl font-bold" style={{ color: result.collision_distributed === 0 ? 'var(--status-success)' : 'var(--status-error)' }}>
                  {result.collision_distributed}
                </span>
                <span className="text-xs text-secondary">Target: 0</span>
              </div>
            </div>
          </div>

          <div className="flex justify-end mt-4" style={{ marginTop: '1rem' }}>
            <button className="btn btn-primary" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
};
