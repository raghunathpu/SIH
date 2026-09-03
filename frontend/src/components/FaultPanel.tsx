import React, { useState } from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
  onInjectLatency: (ticks: number) => void;
  onDropPackets: (prob: number) => void;
}

export const FaultPanel: React.FC<Props> = ({ state, onInjectLatency, onDropPackets }) => {
  const [latency, setLatency] = useState(1);
  const [dropProb, setDropProb] = useState(5);

  if (!state) return null;

  return (
    <div className="card" style={{ background: 'var(--bg-surface-elevated)', flexShrink: 0 }}>
      <div className="card-header">
        <h3 className="font-semibold text-sm tracking-wide text-primary flex items-center gap-2">
          <span>⚡</span> Fault Injection
        </h3>
      </div>
      
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-secondary">Network Latency</span>
            <span className="text-primary font-mono">{latency} ticks</span>
          </div>
          <input 
            type="range" 
            min="1" 
            max="10" 
            value={latency} 
            onChange={(e) => {
              const val = parseInt(e.target.value);
              setLatency(val);
              onInjectLatency(val);
            }}
            className="w-full"
            style={{ accentColor: 'var(--accent-warning)' }}
          />
        </div>

        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-secondary">Packet Loss Prob.</span>
            <span className="text-primary font-mono">{dropProb}%</span>
          </div>
          <input 
            type="range" 
            min="0" 
            max="50" 
            value={dropProb} 
            onChange={(e) => {
              const val = parseInt(e.target.value);
              setDropProb(val);
              onDropPackets(val / 100.0);
            }}
            className="w-full"
            style={{ accentColor: 'var(--accent-danger)' }}
          />
        </div>
      </div>
    </div>
  );
};
