import React, { useEffect, useRef } from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
}

export const LiveEventFeed: React.FC<Props> = ({ state }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [state?.events]);

  if (!state) return null;

  const events = state.events.slice(-50); // Show last 50 events

  const getEventColor = (type: string) => {
    if (type.includes('TASK')) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
    if (type === 'NEGOTIATION') return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    if (type === 'OBSTACLE' || type === 'DEADLOCK' || type === 'COLLISION') return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
    if (type === 'REROUTE') return 'text-blue-400 border-blue-500/30 bg-blue-500/10';
    return 'text-slate-300 border-slate-500/30 bg-slate-500/10';
  };

  const getEventIcon = (type: string) => {
    if (type.includes('TASK')) return '📦';
    if (type === 'NEGOTIATION') return '🤝';
    if (type === 'OBSTACLE') return '🚧';
    if (type === 'DEADLOCK') return '🔄';
    if (type === 'REROUTE') return '↪️';
    if (type === 'COLLISION') return '💥';
    return 'ℹ️';
  };

  return (
    <div className="card" style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div className="card-header flex justify-between items-center">
        <span>Decentralized Decision Log</span>
        <span className="badge badge-success">Recording</span>
      </div>
      <div className="card-body" style={{ overflowY: 'auto', padding: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }} ref={scrollRef}>
        {events.length === 0 ? (
          <div className="text-center text-tertiary mt-4 text-sm">No events yet...</div>
        ) : (
          events.map((ev, i) => (
            <div 
              key={`${ev.tick}-${i}`} 
              style={{ 
                animation: 'slideUp 0.3s ease-out',
                padding: '0.75rem',
                borderRadius: 'var(--radius-sm)',
                borderLeft: '4px solid',
              }}
              className={`text-sm ${getEventColor(ev.event_type)}`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className="font-mono text-xs opacity-70">TICK {ev.tick}</span>
                {ev.robot_id && <span className="font-bold">{ev.robot_id}</span>}
              </div>
              <div className="flex gap-2">
                <span>{getEventIcon(ev.event_type)}</span>
                <span style={{ lineHeight: 1.4 }}>{ev.description}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
