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
  isBenchmarking: boolean;
  onUploadBlueprint: (layout: string[]) => void;
}

export const ControlBar: React.FC<Props> = ({
  state, scenarios, onPlay, onPause, onStep, onReset, onSetSpeed, onLoadScenario, onRunBenchmark, isBenchmarking, onUploadBlueprint
}) => {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.type.startsWith('image/') || file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await fetch(`http://${window.location.hostname}:8000/api/upload_blueprint_file`, {
          method: 'POST',
          body: formData
        });
        const json = await res.json();
        if (json.status === 'error') {
          alert('Blueprint Upload Failed: ' + json.message);
        }
      } catch (err) {
        alert('Blueprint Upload Request Failed. Is the backend running?');
        console.error('Failed to upload file:', err);
      }
    } else {
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        if (text) {
          // Split by lines, trim trailing spaces, ignore empty lines
          const lines = text.split('\n').map(l => l.trimEnd()).filter(l => l.length > 0);
          if (lines.length > 0) {
            onUploadBlueprint(lines);
          }
        }
      };
      reader.readAsText(file);
    }
    
    // Reset input so the same file can be uploaded again if needed
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  if (!state) return null;

  return (
    <div className="control-bar">
      <input 
        type="file" 
        accept=".txt,.json,.csv,image/png,image/jpeg,application/pdf" 
        style={{ display: 'none' }} 
        ref={fileInputRef} 
        onChange={handleFileUpload} 
      />
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

      {/* ── Benchmark & Upload ── */}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button className="btn btn-secondary" onClick={() => fileInputRef.current?.click()} title="Upload Custom Grid Blueprint">
          📁 Upload Map
        </button>
        <button className="btn btn-benchmark" onClick={onRunBenchmark} disabled={isBenchmarking}>
          {isBenchmarking ? '⏳ Running...' : '📊 Benchmark'}
        </button>
      </div>
    </div>
  );
};
