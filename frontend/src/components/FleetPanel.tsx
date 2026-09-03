import React from 'react';
import type { SimulationState } from '../types';

interface FleetPanelProps {
  state: SimulationState | null;
  onSelectRobot: (robotId: string) => void;
  selectedRobotId: string | null;
}

export const FleetPanel: React.FC<FleetPanelProps> = ({ state, onSelectRobot, selectedRobotId }) => {
  if (!state) return <div className="card h-full"><div className="card-header">Fleet</div><div className="card-body">Waiting for simulation data...</div></div>;

  const robots = Object.values(state.robots);

  return (
    <div className="card" style={{ flex: 1, minHeight: 0 }}>
      <div className="card-header">
        <span>Active Fleet</span>
        <span className="badge badge-success">
          {robots.length} AMRs
        </span>
      </div>
      <div className="card-body" style={{ padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {robots.map(robot => (
          <div 
            key={robot.robot_id}
            onClick={() => onSelectRobot(robot.robot_id)}
            style={{
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              background: selectedRobotId === robot.robot_id ? 'var(--bg-surface-hover)' : 'var(--bg-surface-elevated)',
              border: `1px solid ${selectedRobotId === robot.robot_id ? 'var(--border-focus)' : 'var(--border-color)'}`,
              boxShadow: selectedRobotId === robot.robot_id ? 'var(--shadow-glow)' : 'none',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem',
              transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)'
            }}
            className="hover:-translate-y-0.5 hover:border-white/20"
          >
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <div style={{ width: '14px', height: '14px', borderRadius: '50%', background: robot.color, boxShadow: `0 0 10px ${robot.color}` }}></div>
                <span className="font-bold text-lg font-mono tracking-tight">{robot.robot_id}</span>
              </div>
              <span className="text-xs font-semibold tracking-wider px-2 py-1 rounded" style={{ 
                background: 'rgba(255,255,255,0.05)',
                color: robot.status === 'MOVING' ? 'var(--status-success)' : 
                       robot.status === 'WAITING' || robot.status === 'NEGOTIATING' || robot.status === 'APPROACHING_CONFLICT' ? 'var(--status-warning)' : 
                       robot.status === 'BLOCKED' || robot.status === 'UNAVAILABLE' ? 'var(--status-error)' : 'var(--text-secondary)'
              }}>
                {robot.status}
              </span>
            </div>
            
            <div className="flex justify-between text-sm text-secondary font-mono">
              <span className="flex items-center gap-1"><span className="text-emerald-400">⚡</span> {robot.battery.toFixed(0)}%</span>
              <span className="flex items-center gap-1"><span className="text-blue-400">📦</span> {robot.current_task || 'IDLE'}</span>
            </div>
            
            <div className="progress-bg mt-1">
              <div 
                className="progress-fill" 
                style={{ 
                  width: `${robot.battery}%`,
                  background: robot.battery < 20 ? 'var(--status-error)' : robot.battery < 50 ? 'var(--status-warning)' : 'var(--status-success)',
                  boxShadow: `0 0 10px ${robot.battery < 20 ? 'var(--status-error)' : robot.battery < 50 ? 'var(--status-warning)' : 'var(--status-success)'}`
                }}
              ></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
