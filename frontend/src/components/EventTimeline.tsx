import React from 'react';
import type { SimulationState } from '../types';

export const EventTimeline: React.FC<{ state: SimulationState | null }> = ({ state }) => {
  if (!state) return null;

  // Show last 50 events in reverse chronological order
  const events = [...state.events].reverse().slice(0, 50);

  return (
    <div className="card flex-1 mt-4" style={{ display: 'flex', flexDirection: 'column', marginTop: '1rem', flex: 1, minHeight: 0 }}>
      <div className="card-header">
        Event Feed
      </div>
      <div className="card-body" style={{ padding: '0.5rem', overflowY: 'auto' }}>
        <div className="flex flex-col gap-2">
          {events.map((ev, i) => (
            <div key={i} className="flex gap-2 text-sm items-start" style={{ padding: '0.5rem', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)' }}>
              <span className="font-mono text-tertiary" style={{ minWidth: '40px' }}>T{ev.tick}</span>
              <span 
                className="font-semibold" 
                style={{ 
                  color: ev.event_type === 'COLLISION' || ev.event_type === 'DEADLOCK' ? 'var(--status-error)' : 
                         ev.event_type === 'TASK' ? 'var(--status-success)' :
                         ev.event_type === 'NEGOTIATION' ? 'var(--status-info)' : 'var(--accent-primary)',
                  minWidth: '80px'
                }}
              >
                {ev.event_type}
              </span>
              {ev.robot_id && <span className="font-mono">{ev.robot_id}</span>}
              <span className="text-secondary flex-1">{ev.description}</span>
            </div>
          ))}
          {events.length === 0 && (
            <div className="text-tertiary text-center p-4">No events yet...</div>
          )}
        </div>
      </div>
    </div>
  );
};
