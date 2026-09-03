import React from 'react';
import type { SimulationState, ScenarioInfo } from '../types';

interface ControlBarProps {
  state: SimulationState | null;
  scenarios: ScenarioInfo[];
  onPlay: () => void;
  onPause: () => void;
  onStep: () => void;
  onReset: () => void;
  onSetSpeed: (speed: number) => void;
  onLoadScenario: (scenario: string, baseline: boolean) => void;
  onRunBenchmark: () => void;
}

export const ControlBar: React.FC<ControlBarProps> = ({
  state, scenarios, onPlay, onPause, onStep, onReset, onSetSpeed, onLoadScenario, onRunBenchmark
}) => {
  const isRunning = state?.running || false;

  return (
    <div className="card" style={{ padding: '0.75rem', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
      <div className="flex gap-2 items-center">
        <select 
          className="btn btn-secondary" 
          value={state?.scenario || ''} 
          onChange={(e) => onLoadScenario(e.target.value, false)}
          style={{ width: '200px' }}
        >
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.id}: {s.name}</option>
          ))}
        </select>
        
        <div className="flex bg-surface-elevated rounded overflow-hidden border border-color" style={{ borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', display: 'flex' }}>
          <button 
            className={`px-3 py-1 text-sm ${!state?.baseline_mode ? 'bg-accent text-white' : 'text-secondary hover:text-primary'}`}
            style={{ padding: '0.25rem 0.75rem', background: !state?.baseline_mode ? 'var(--accent-primary)' : 'transparent', color: !state?.baseline_mode ? 'white' : 'inherit', border: 'none', cursor: 'pointer' }}
            onClick={() => { if (state?.scenario) onLoadScenario(state.scenario, false); }}
          >
            Distributed
          </button>
          <button 
            className={`px-3 py-1 text-sm ${state?.baseline_mode ? 'bg-accent text-white' : 'text-secondary hover:text-primary'}`}
            style={{ padding: '0.25rem 0.75rem', background: state?.baseline_mode ? 'var(--accent-primary)' : 'transparent', color: state?.baseline_mode ? 'white' : 'inherit', border: 'none', cursor: 'pointer' }}
            onClick={() => { if (state?.scenario) onLoadScenario(state.scenario, true); }}
          >
            Baseline
          </button>
        </div>
      </div>

      <div className="flex gap-2 items-center">
        <button className="btn btn-secondary" onClick={() => onReset()}>
          Reset
        </button>
        <button className="btn btn-secondary" onClick={() => onStep()} disabled={isRunning}>
          Step
        </button>
        {isRunning ? (
          <button className="btn btn-primary" onClick={() => onPause()}>Pause</button>
        ) : (
          <button className="btn btn-primary" onClick={() => onPlay()}>Play</button>
        )}
      </div>

      <div className="flex gap-4 items-center">
        <div className="flex items-center gap-2">
          <span className="text-sm text-tertiary">Speed</span>
          <input 
            type="range" 
            min="1" max="50" 
            value={state?.speed || 10} 
            onChange={(e) => onSetSpeed(parseInt(e.target.value))}
            style={{ width: '100px' }}
          />
        </div>
        
        <button className="btn btn-primary" onClick={() => onRunBenchmark()} style={{ background: '#8b5cf6' }}>
          Run Benchmark
        </button>
      </div>
    </div>
  );
};
