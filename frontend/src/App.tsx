import { useState } from 'react';
import { useSimulation } from './useSimulation';
import WarehouseCanvas from './components/WarehouseCanvas';
import { FleetPanel } from './components/FleetPanel';
import { FaultPanel } from './components/FaultPanel';
import { RobotDetail } from './components/RobotDetail';
import { LiveEventFeed } from './components/LiveEventFeed';
import { ControlBar } from './components/ControlBar';
import { MetricsBar } from './components/MetricsBar';
import { BenchmarkView } from './components/BenchmarkView';
import { NetworkTopologyView } from './components/NetworkTopologyView';
import { TelemetryGrid } from './components/TelemetryGrid';
import './index.css';

type Tab = 'WAREHOUSE' | 'NETWORK' | 'TELEMETRY';

function App() {
  const sim = useSimulation();
  const [selectedRobotId, setSelectedRobotId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('WAREHOUSE');

  return (
    <>
      <header className="header">
        <div className="header-title">
          <div className="header-logo">FM</div>
          <div>
            <h2 className="text-xl">FleetMind</h2>
            <div className="text-xs text-secondary font-mono">Edge-AI Orchestration</div>
          </div>
        </div>
        
        <div className="header-tabs">
          <button className={`header-tab ${activeTab === 'WAREHOUSE' ? 'active' : ''}`} onClick={() => setActiveTab('WAREHOUSE')}>
            Grid View
          </button>
          <button className={`header-tab ${activeTab === 'NETWORK' ? 'active' : ''}`} onClick={() => setActiveTab('NETWORK')}>
            P2P Network
          </button>
          <button className={`header-tab ${activeTab === 'TELEMETRY' ? 'active' : ''}`} onClick={() => setActiveTab('TELEMETRY')}>
            Hardware Telemetry
          </button>
        </div>

        <div className="flex gap-4 items-center">
          <div className="flex items-center gap-2 bg-surface-elevated px-3 py-1.5 rounded-full border border-white/5">
            <span className={`status-dot ${sim.connected ? 'active' : 'inactive'}`}></span>
            <span className="text-sm text-secondary font-medium">{sim.connected ? 'WebSocket Active' : 'Offline'}</span>
          </div>
        </div>
      </header>

      <main className="main-content">
        <aside className="sidebar-left">
          <FleetPanel state={sim.state} onSelectRobot={setSelectedRobotId} selectedRobotId={selectedRobotId} />
          <FaultPanel state={sim.state} onInjectLatency={sim.injectLatency} onDropPackets={sim.dropPackets} />
        </aside>

        <section className="center-panel">
          <ControlBar 
            state={sim.state} 
            scenarios={sim.scenarios}
            onPlay={sim.play}
            onPause={sim.pause}
            onStep={sim.step}
            onReset={sim.reset}
            onSetSpeed={sim.setSpeed}
            onLoadScenario={sim.loadScenario}
            onRunBenchmark={sim.runBenchmark}
          />
          
          <MetricsBar state={sim.state} />
          
          <div className="canvas-container" style={{ display: activeTab === 'WAREHOUSE' ? 'block' : 'none' }}>
            <WarehouseCanvas 
              state={sim.state} 
              selectedRobot={selectedRobotId}
              onSelectRobot={setSelectedRobotId}
              onCellClick={sim.injectObstacle}
            />
          </div>

          <div style={{ display: activeTab === 'NETWORK' ? 'block' : 'none', flex: 1 }}>
            <NetworkTopologyView state={sim.state} />
          </div>

          <div style={{ display: activeTab === 'TELEMETRY' ? 'block' : 'none', flex: 1 }}>
            <TelemetryGrid state={sim.state} />
          </div>
        </section>

        <aside className="sidebar-right">
          {selectedRobotId ? (
            <RobotDetail state={sim.state} robotId={selectedRobotId} />
          ) : (
            <LiveEventFeed state={sim.state} />
          )}
        </aside>
      </main>

      {sim.benchmark && (
        <BenchmarkView result={sim.benchmark} onClose={() => sim.reset()} />
      )}
    </>
  );
}

export default App;
