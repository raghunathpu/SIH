import React from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
}

export const TelemetryGrid: React.FC<Props> = ({ state }) => {
  if (!state) return <div className="card h-full"><div className="card-body">Waiting for data...</div></div>;

  const robots = Object.values(state.robots);

  return (
    <div className="card h-full" style={{ height: '100%' }}>
      <div className="card-header flex justify-between items-center">
        <h2 className="text-lg text-primary">Edge Hardware Telemetry</h2>
        <div className="badge badge-success">Live Network</div>
      </div>
      <div className="card-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1rem' }}>
        {robots.map(r => (
          <div key={r.robot_id} style={{ 
            background: 'var(--bg-surface-elevated)', 
            border: '1px solid var(--border-color)', 
            borderRadius: 'var(--radius-md)', 
            padding: '1rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '1rem'
          }}>
            <div className="flex justify-between items-center border-b border-white/5 pb-2">
              <div className="flex items-center gap-2">
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: r.color, boxShadow: `0 0 8px ${r.color}` }}></div>
                <span className="font-bold text-lg">{r.robot_id}</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${r.status === 'UNAVAILABLE' ? 'bg-red-500/20 text-red-500' : 'bg-emerald-500/20 text-emerald-500'}`}>
                {r.status === 'UNAVAILABLE' ? 'OFFLINE' : 'ONLINE'}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              {/* CPU Gauge */}
              <div className="flex flex-col items-center gap-1">
                <span className="text-xs text-secondary">CPU Usage</span>
                <div className="gauge-container">
                  <svg className="gauge-svg" viewBox="0 0 100 100">
                    <circle className="gauge-bg" cx="50" cy="50" r="40" />
                    <circle 
                      className="gauge-fill" 
                      cx="50" cy="50" r="40" 
                      stroke={r.hardware.cpu > 80 ? 'var(--status-error)' : r.hardware.cpu > 50 ? 'var(--status-warning)' : 'var(--accent-primary)'}
                      strokeDasharray="251.2"
                      strokeDashoffset={251.2 - (251.2 * r.hardware.cpu) / 100}
                    />
                  </svg>
                  <span className="gauge-text">{Math.round(r.hardware.cpu)}%</span>
                </div>
              </div>

              {/* Thermal Gauge */}
              <div className="flex flex-col items-center gap-1">
                <span className="text-xs text-secondary">Thermal</span>
                <div className="gauge-container">
                  <svg className="gauge-svg" viewBox="0 0 100 100">
                    <circle className="gauge-bg" cx="50" cy="50" r="40" />
                    <circle 
                      className="gauge-fill" 
                      cx="50" cy="50" r="40" 
                      stroke={r.hardware.thermal > 65 ? 'var(--status-error)' : r.hardware.thermal > 50 ? 'var(--status-warning)' : 'var(--status-success)'}
                      strokeDasharray="251.2"
                      strokeDashoffset={251.2 - (251.2 * Math.min(100, (r.hardware.thermal / 80) * 100)) / 100}
                    />
                  </svg>
                  <span className="gauge-text">{Math.round(r.hardware.thermal)}°C</span>
                </div>
              </div>
            </div>

            {/* RAM & Network */}
            <div className="flex flex-col gap-2 mt-2">
              <div className="flex justify-between items-end">
                <span className="text-xs text-secondary">Memory (MB)</span>
                <span className="text-sm font-mono">{r.hardware.ram.toFixed(1)} / 512</span>
              </div>
              <div className="progress-bg"><div className="progress-fill bg-indigo-500" style={{ width: `${(r.hardware.ram / 512) * 100}%` }}></div></div>

              <div className="flex justify-between items-end mt-2">
                <span className="text-xs text-secondary">Network Latency</span>
                <span className="text-sm font-mono text-emerald-400">{r.hardware.latency.toFixed(1)} ms</span>
              </div>
            </div>

          </div>
        ))}
      </div>
    </div>
  );
};
