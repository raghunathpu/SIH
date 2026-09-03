import React from 'react';
import type { SimulationState, ScenarioInfo } from '../types';

interface Props {
  state: SimulationState | null;
  scenarios: ScenarioInfo[];
  onPlay: () => void;
  onPause: () => void;
  onStep: () => void;
  onReset: () => void;
  onSetSpeed: (speed: number) => void;
  onLoadScenario: (id: string, baseline?: boolean) => void;
  onRunBenchmark: () => void;
}

export const ControlBar: React.FC<Props> = ({
  state, scenarios, onPlay, onPause, onStep, onReset, onSetSpeed, onLoadScenario, onRunBenchmark
}) => {
  if (!state) return null;

  return (
    <div className="card" style={{ padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface-elevated)' }}>
      
      <div className="flex items-center gap-4">
        <select 
          className="bg-surface border border-color rounded px-3 py-1.5 text-sm font-medium outline-none focus:border-blue-500"
          value={state.scenario || ''} 
          onChange={(e) => onLoadScenario(e.target.value, state.baseline_mode)}
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', borderRadius: 'var(--radius-sm)' }}
        >
          <option value="" disabled>Select Scenario...</option>
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        
        <div className="flex items-center gap-2 bg-surface p-1 rounded-md border border-color" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
          <button 
            className={`px-3 py-1 text-sm rounded font-medium transition-colors ${!state.baseline_mode ? 'bg-indigo-500/20 text-indigo-400' : 'text-secondary hover:text-primary'}`}
            onClick={() => onLoadScenario(state.scenario || '01_BASIC', false)}
          >
            Distributed
          </button>
          <button 
            className={`px-3 py-1 text-sm rounded font-medium transition-colors ${state.baseline_mode ? 'bg-amber-500/20 text-amber-400' : 'text-secondary hover:text-primary'}`}
            onClick={() => onLoadScenario(state.scenario || '01_BASIC', true)}
            title="Legacy central planning (stop-and-wait)"
          >
            Baseline
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1 bg-surface p-1 rounded border border-color" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)' }}>
          <button className="btn btn-secondary" style={{ padding: '0.25rem 0.75rem' }} onClick={onReset} title="Reset">⏮️</button>
          <button className="btn btn-secondary" style={{ padding: '0.25rem 0.75rem' }} onClick={onStep} disabled={state.running} title="Step Forward">⏭️</button>
          {state.running ? (
            <button className="btn btn-primary" style={{ padding: '0.25rem 1rem' }} onClick={onPause} title="Pause (Space)">⏸️ Pause</button>
          ) : (
            <button className="btn btn-primary" style={{ padding: '0.25rem 1rem' }} onClick={onPlay} title="Play (Space)">▶️ Play</button>
          )}
        </div>

        <div className="flex items-center gap-2 ml-4">
          <span className="text-xs text-secondary font-mono">SPEED {state.speed}x</span>
          <input 
            type="range" 
            min="1" max="100" 
            value={state.speed} 
            onChange={(e) => onSetSpeed(parseInt(e.target.value))}
            style={{ width: '100px', accentColor: 'var(--accent-primary)' }}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button className="btn btn-primary bg-gradient-to-r from-emerald-500 to-teal-500 border-none shadow-lg shadow-emerald-500/20" onClick={onRunBenchmark}>
          📊 Run Benchmark
        </button>
      </div>
      
    </div>
  );
};
