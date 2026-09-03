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
    <div className="card" style={{ height: '100%' }}>
      <div className="card-header">
        <span>Active Fleet</span>
        <span className="text-xs bg-surface-elevated px-2 py-1 rounded" style={{ background: 'var(--bg-surface-elevated)', padding: '2px 6px', borderRadius: '4px' }}>
          {robots.length} AMRs
        </span>
      </div>
      <div className="card-body" style={{ padding: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {robots.map(robot => (
          <div 
            key={robot.robot_id}
            onClick={() => onSelectRobot(robot.robot_id)}
            style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              background: selectedRobotId === robot.robot_id ? 'var(--bg-surface-hover)' : 'rgba(255,255,255,0.02)',
              border: `1px solid ${selectedRobotId === robot.robot_id ? 'var(--border-focus)' : 'var(--border-color)'}`,
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
              transition: 'all 0.2s'
            }}
          >
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: robot.color }}></div>
                <span className="font-semibold">{robot.robot_id}</span>
              </div>
              <span className="text-xs text-secondary" style={{ 
                color: robot.status === 'MOVING' ? 'var(--status-success)' : 
                       robot.status === 'WAITING' || robot.status === 'BLOCKED' ? 'var(--status-warning)' : 
                       robot.status === 'UNAVAILABLE' ? 'var(--status-error)' : 'var(--text-secondary)'
              }}>
                {robot.status}
              </span>
            </div>
            
            <div className="flex justify-between text-xs text-tertiary">
              <span>Bat: {robot.battery.toFixed(0)}%</span>
              <span>Task: {robot.current_task || 'None'}</span>
            </div>
            
            <div className="progress-bg">
              <div 
                className="progress-fill" 
                style={{ 
                  width: `${robot.battery}%`,
                  background: robot.battery < 20 ? 'var(--status-error)' : robot.battery < 50 ? 'var(--status-warning)' : 'var(--status-success)'
                }}
              ></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
