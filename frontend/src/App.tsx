import { useState } from 'react';
import { useSimulation } from './useSimulation';
import WarehouseCanvas from './components/WarehouseCanvas';
import { FleetPanel } from './components/FleetPanel';
import { RobotDetail } from './components/RobotDetail';
import { EventTimeline } from './components/EventTimeline';
import { ControlBar } from './components/ControlBar';
import { MetricsBar } from './components/MetricsBar';
import { BenchmarkView } from './components/BenchmarkView';
import './index.css';

function App() {
  const sim = useSimulation();
  const [selectedRobotId, setSelectedRobotId] = useState<string | null>(null);
  const [showArchitecture, setShowArchitecture] = useState(false);

  return (
    <>
      {/* Header */}
      <header className="header">
        <div className="header-title">
          <div className="header-logo">FM</div>
          <h2>FleetMind <span className="text-sm font-normal text-tertiary ml-2">Distributed AMR Coordination</span></h2>
        </div>
        
        <div className="flex gap-4 items-center">
          <div className="flex items-center gap-2">
            <span className={`status-dot ${sim.connected ? 'active' : 'inactive'}`}></span>
            <span className="text-sm text-secondary">{sim.connected ? 'Connected' : 'Disconnected'}</span>
          </div>
          <button className="btn btn-secondary" onClick={() => setShowArchitecture(true)}>Architecture</button>
        </div>
      </header>

      {/* Main Layout */}
      <main className="main-content">
        {/* Left Sidebar */}
        <aside className="sidebar-left">
          <FleetPanel state={sim.state} onSelectRobot={setSelectedRobotId} selectedRobotId={selectedRobotId} />
        </aside>

        {/* Center Panel (Canvas + Controls) */}
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
          
          <div className="canvas-container">
            <WarehouseCanvas 
              state={sim.state} 
              selectedRobot={selectedRobotId}
              onSelectRobot={setSelectedRobotId}
              onCellClick={sim.injectObstacle}
            />
          </div>
        </section>

        {/* Right Sidebar */}
        <aside className="sidebar-right">
          <RobotDetail state={sim.state} robotId={selectedRobotId} />
          <EventTimeline state={sim.state} />
        </aside>
      </main>

      {/* Benchmark Modal */}
      {sim.benchmark && (
        <BenchmarkView result={sim.benchmark} onClose={() => sim.reset()} />
      )}

      {/* Architecture Modal */}
      {showArchitecture && (
        <div className="modal-overlay" onClick={() => setShowArchitecture(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>System Architecture</h2>
              <button className="close-btn" onClick={() => setShowArchitecture(false)}>×</button>
            </div>
            <div className="modal-body text-secondary" style={{ lineHeight: '1.6' }}>
              <h3 className="text-primary mb-2" style={{ marginBottom: '0.5rem' }}>Edge-AI Distributed Coordination</h3>
              <p style={{ marginBottom: '1rem' }}>
                FleetMind replaces traditional centralized orchestration (which suffers from latency and single points of failure) with a decentralized, multi-agent system.
              </p>
              
              <h3 className="text-primary mb-2" style={{ marginBottom: '0.5rem', marginTop: '1.5rem' }}>Core Components</h3>
              <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <li><strong>Peer-to-Peer Message Bus:</strong> Simulates high-bandwidth local networking (e.g., 5G/Wi-Fi 6) for AMRs to exchange intents, state updates, and negotiate space.</li>
                <li><strong>Robot Agent:</strong> Each AMR runs an independent decision cycle: Sense (peer knowledge), Plan (A* pathfinding), Act (move).</li>
                <li><strong>Conflict Resolution:</strong> AMRs detect impending collisions based on shared planned paths. Priority and physical constraints resolve who yields and who proceeds.</li>
                <li><strong>Deadlock Recovery:</strong> Distributed cycle detection over a wait-for graph identifies deadlocks. The lowest priority robot yields and dynamically reroutes.</li>
              </ul>

              <h3 className="text-primary mb-2" style={{ marginBottom: '0.5rem', marginTop: '1.5rem' }}>Performance Benchmark</h3>
              <p>
                The system requires a &gt;= 20% improvement in task completion time compared to a naive Stop-and-Wait baseline approach, while guaranteeing 0 collisions.
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default App;
