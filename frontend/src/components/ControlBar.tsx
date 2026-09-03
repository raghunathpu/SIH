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
    <div className="control-bar">
      {/* ── Scenario & Mode ── */}
      <div className="control-group">
        <select
          className="control-select"
          value={state.scenario || ''}
          onChange={(e) => onLoadScenario(e.target.value, state.baseline_mode)}
        >
          <option value="" disabled>Scenario...</option>
          {scenarios.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>

        <div className="mode-toggle">
          <button
            className={`mode-btn ${!state.baseline_mode ? 'mode-btn-active-distributed' : ''}`}
            onClick={() => onLoadScenario(state.scenario || '01_BASIC', false)}
          >
            Distributed
          </button>
          <button
            className={`mode-btn ${state.baseline_mode ? 'mode-btn-active-baseline' : ''}`}
            onClick={() => onLoadScenario(state.scenario || '01_BASIC', true)}
            title="Legacy central planning (stop-and-wait)"
          >
            Baseline
          </button>
        </div>
      </div>

      {/* ── Playback Controls ── */}
      <div className="control-group">
        <div className="playback-group">
          <button className="btn btn-secondary btn-icon" onClick={onReset} title="Reset">⏮️</button>
          <button className="btn btn-secondary btn-icon" onClick={onStep} disabled={state.running} title="Step Forward">⏭️</button>
          {state.running ? (
            <button className="btn btn-primary btn-compact" onClick={onPause} title="Pause (Space)">⏸️ Pause</button>
          ) : (
            <button className="btn btn-primary btn-compact" onClick={onPlay} title="Play (Space)">▶️ Play</button>
          )}
        </div>

        <div className="speed-control">
          <span className="speed-label">{state.speed}x</span>
          <input
            type="range"
            min="1" max="100"
            value={state.speed}
            onChange={(e) => onSetSpeed(parseInt(e.target.value))}
            className="speed-slider"
          />
        </div>
      </div>

      {/* ── Benchmark ── */}
      <button className="btn btn-benchmark" onClick={onRunBenchmark}>
        📊 Benchmark
      </button>
    </div>
  );
};
