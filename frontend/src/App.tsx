import { useState, useCallback, useRef } from 'react';
import { useSimulation } from './useSimulation';
import WarehouseCanvas from './components/WarehouseCanvas';
import { FleetPanel } from './components/FleetPanel';
import { FaultPanel } from './components/FaultPanel';
import { TaskPanel } from './components/TaskPanel';
import { RobotDetail } from './components/RobotDetail';
import { LiveEventFeed } from './components/LiveEventFeed';
import { ControlBar } from './components/ControlBar';
import { MetricsBar } from './components/MetricsBar';
import { BenchmarkView } from './components/BenchmarkView';
import { NetworkTopologyView } from './components/NetworkTopologyView';
import { TelemetryGrid } from './components/TelemetryGrid';
import type { ClickMode } from './types';
import './index.css';

type Tab = 'WAREHOUSE' | 'NETWORK' | 'TELEMETRY';

function App() {
  const sim = useSimulation();
  const [selectedRobotId, setSelectedRobotId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('WAREHOUSE');
  const [clickMode, setClickMode] = useState<ClickMode>('OBSTACLE');

  // Dead zone drag state (grid coordinates)
  const [deadZoneDragStart, setDeadZoneDragStart] = useState<{ x: number; y: number } | null>(null);
  const [deadZoneDragEnd, setDeadZoneDragEnd] = useState<{ x: number; y: number } | null>(null);

  /** Route grid cell clicks based on the active click mode */
  const handleCellClick = useCallback((x: number, y: number) => {
    if (!sim.state) return;

    if (clickMode === 'ROBOT') {
      const robotEntry = Object.entries(sim.state.robots).find(
        ([_, r]) => r.position[0] === x && r.position[1] === y
      );
      if (robotEntry) {
        sim.removeRobot(robotEntry[0]);
      } else {
        sim.addRobot(x, y);
      }
    } else if (clickMode === 'DEAD_ZONE') {
      // Single-click on existing dead zone removes it
      const existingZone = sim.state.dead_zones?.find(
        ([x1, y1, x2, y2]) => x >= x1 && x <= x2 && y >= y1 && y <= y2
      );
      if (existingZone) {
        sim.removeDeadZone(existingZone[0], existingZone[1], existingZone[2], existingZone[3]);
      }
      // Drag-to-draw is handled by onDeadZoneDraw below
    } else {
      const isObstacle = sim.state.warehouse.dynamic_obstacles.some(
        obs => obs[0] === x && obs[1] === y
      );
      if (isObstacle) {
        sim.removeObstacle(x, y);
      } else {
        sim.injectObstacle(x, y);
      }
    }
  }, [clickMode, sim]);

  /** Called when user finishes dragging to draw a dead zone */
  const handleDeadZoneDraw = useCallback((x1: number, y1: number, x2: number, y2: number) => {
    sim.addDeadZone(
      Math.min(x1, x2), Math.min(y1, y2),
      Math.max(x1, x2), Math.max(y1, y2)
    );
  }, [sim.addDeadZone]);

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
          {/* Click mode toggle — only relevant in Grid View */}
          {activeTab === 'WAREHOUSE' && (
            <div className="click-mode-toggle">
              <button
                id="click-mode-obstacle"
                className={`click-mode-btn ${clickMode === 'OBSTACLE' ? 'active-obstacle' : ''}`}
                onClick={() => setClickMode('OBSTACLE')}
                title="Click grid cells to place/remove obstacles"
              >
                🧱 Obstacle
              </button>
              <button
                id="click-mode-robot"
                className={`click-mode-btn ${clickMode === 'ROBOT' ? 'active-robot' : ''}`}
                onClick={() => setClickMode('ROBOT')}
                title="Click grid cells to deploy/remove robots"
              >
                🤖 Robot
              </button>
              <button
                id="click-mode-deadzone"
                className={`click-mode-btn ${clickMode === 'DEAD_ZONE' ? 'active-deadzone' : ''}`}
                onClick={() => setClickMode('DEAD_ZONE')}
                title="Click and drag to draw Wi-Fi dead zones"
              >
                📡 Dead Zone
              </button>
            </div>
          )}

          <div className="flex items-center gap-2 bg-surface-elevated px-3 py-1.5 rounded-full border border-white/5">
            <span className={`status-dot ${sim.connected ? 'active' : 'inactive'}`}></span>
            <span className="text-sm text-secondary font-medium">{sim.connected ? 'WebSocket Active' : 'Offline'}</span>
          </div>
        </div>
      </header>

      <main className="main-content">
        <aside className="sidebar-left">
          <FleetPanel state={sim.state} onSelectRobot={setSelectedRobotId} selectedRobotId={selectedRobotId} />
          <TaskPanel onAddTask={sim.addTask} state={sim.state} />
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
            isBenchmarking={sim.isBenchmarking}
            onUploadBlueprint={sim.uploadBlueprint}
          />
          
          <MetricsBar state={sim.state} />
          
          <div className="canvas-container" style={{ display: activeTab === 'WAREHOUSE' ? 'block' : 'none' }}>
            <WarehouseCanvas 
              state={sim.state} 
              selectedRobot={selectedRobotId}
              onSelectRobot={setSelectedRobotId}
              onCellClick={handleCellClick}
              clickMode={clickMode}
              onDeadZoneDraw={handleDeadZoneDraw}
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
