import React from 'react';
import type { SimulationState } from '../types';

interface RobotDetailProps {
  state: SimulationState | null;
  robotId: string | null;
}

export const RobotDetail: React.FC<RobotDetailProps> = ({ state, robotId }) => {
  if (!state || !robotId) return null;
  
  const robot = state.robots[robotId];
  if (!robot) return null;

  return (
    <div className="card" style={{ marginTop: '1rem' }}>
      <div className="card-header">
        Telemetry: {robot.robot_id}
      </div>
      <div className="card-body flex-col gap-3">
        <div className="flex justify-between text-sm">
          <span className="text-tertiary">Position</span>
          <span className="font-mono">({robot.position[0]}, {robot.position[1]})</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-tertiary">Destination</span>
          <span className="font-mono">{robot.destination ? `(${robot.destination[0]}, ${robot.destination[1]})` : 'None'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-tertiary">Priority</span>
          <span className="font-mono">{robot.priority}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-tertiary">Intent</span>
          <span className="text-secondary">{robot.intent || 'Idle'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-tertiary">Wait Time</span>
          <span className="font-mono">{robot.waiting_time} ticks</span>
        </div>
        
        <div className="mt-2 text-xs bg-surface-elevated p-2 rounded" style={{ background: 'var(--bg-surface-elevated)', padding: '0.5rem', borderRadius: 'var(--radius-sm)' }}>
          <div className="text-tertiary mb-1">Edge Diagnostics (Hardware Profiling)</div>
          <div className="grid grid-cols-2 gap-2 mt-2">
            <div>
              <span className="text-tertiary">CPU: </span>
              <span className={`font-mono ${robot.hardware?.cpu > 80 ? 'text-error' : 'text-primary'}`}>
                {robot.hardware?.cpu?.toFixed(1) ?? 'N/A'}%
              </span>
            </div>
            <div>
              <span className="text-tertiary">RAM: </span>
              <span className="font-mono text-primary">{robot.hardware?.ram?.toFixed(1) ?? 'N/A'} MB</span>
            </div>
            <div>
              <span className="text-tertiary">NET: </span>
              <span className={`font-mono ${robot.hardware?.latency > 8 ? 'text-warning' : 'text-primary'}`}>
                {robot.hardware?.latency?.toFixed(1) ?? 'N/A'} ms
              </span>
            </div>
            <div>
              <span className="text-tertiary">TMP: </span>
              <span className={`font-mono ${robot.hardware?.thermal > 60 ? 'text-error' : 'text-primary'}`}>
                {robot.hardware?.thermal?.toFixed(1) ?? 'N/A'} °C
              </span>
            </div>
          </div>
        </div>

        {robot.decision_reason && (
          <div className="mt-2 text-xs bg-surface-elevated p-2 rounded" style={{ background: 'var(--bg-surface-elevated)', padding: '0.5rem', borderRadius: 'var(--radius-sm)' }}>
            <div className="text-tertiary mb-1">Last Decision</div>
            <div className="text-primary">{robot.decision_reason}</div>
          </div>
        )}

        {robot.status !== 'UNAVAILABLE' && (
          <button 
            className="btn btn-danger w-full mt-2" 
            style={{ 
              background: 'var(--color-error)', 
              color: 'black', 
              border: 'none', 
              padding: '0.5rem', 
              borderRadius: 'var(--radius-md)', 
              cursor: 'pointer',
              fontWeight: 'bold',
              textTransform: 'uppercase',
              fontSize: '0.75rem',
              letterSpacing: '0.05em'
            }}
            onClick={() => {
              fetch(`/api/fail_robot/${robot.robot_id}`, { method: 'POST' })
                .then(res => res.text())
                .then(text => {
                  if (text) console.log('Failover triggered:', JSON.parse(text));
                  else console.log('Failover triggered (no response body)');
                })
                .catch(err => console.error('Failed to trigger failover:', err));
            }}
          >
            Simulate Hardware Failure
          </button>
        )}
        {robot.status === 'UNAVAILABLE' && (
          <div className="text-error text-center mt-2 font-bold text-sm bg-error/10 p-2 rounded">
            ROBOT OFFLINE - TASKS REASSIGNED
          </div>
        )}
      </div>
    </div>
  );
};
