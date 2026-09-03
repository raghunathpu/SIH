import { useCallback, useEffect, useRef, useState } from 'react';
import type { SimulationState, BenchmarkComparison, ScenarioInfo } from './types';

const WS_URL = `ws://${window.location.hostname}:8000/ws`;
const API_URL = `http://${window.location.hostname}:8000/api`;

export function useSimulation() {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<SimulationState | null>(null);
  const [connected, setConnected] = useState(false);
  const [benchmark, setBenchmark] = useState<BenchmarkComparison | null>(null);
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const reconnectTimer = useRef<number | null>(null);

  // Fetch scenarios on mount
  useEffect(() => {
    fetch(`${API_URL}/scenarios`)
      .then(r => r.json())
      .then(setScenarios)
      .catch(() => {});
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      setConnected(true);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'benchmark_result') {
          setBenchmark(data.data);
        } else {
          setState(prev => {
            if (prev && !data.warehouse) {
              data.warehouse = prev.warehouse;
            }
            return data;
          });
        }
      } catch {}
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      // Auto-reconnect
      reconnectTimer.current = window.setTimeout(connect, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (document.activeElement?.tagName === 'INPUT') return;
      
      if (e.code === 'Space') {
        e.preventDefault();
        setState(s => {
          if (s) {
             if (s.running) send('pause');
             else send('play');
          }
          return s;
        });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const send = useCallback((action: string, data?: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Defensive check against passing React events or circular structures
      if (data && (data._reactName || data.nativeEvent || data instanceof Event)) {
        data = {};
      }
      wsRef.current.send(JSON.stringify({ action, ...data }));
    }
  }, []);

  // Control functions
  const play = useCallback(() => send('play'), [send]);
  const pause = useCallback(() => send('pause'), [send]);
  const step = useCallback(() => send('step'), [send]);
  const reset = useCallback(() => { send('reset'); setBenchmark(null); }, [send]);
  const setSpeed = useCallback((speed: number) => send('set_speed', { speed }), [send]);
  const loadScenario = useCallback((scenario: string, baseline?: boolean) =>
    send('load_scenario', { scenario, baseline }), [send]);
  const injectObstacle = useCallback((x: number, y: number) =>
    send('inject_obstacle', { x, y }), [send]);
  const removeObstacle = useCallback((x: number, y: number) =>
    send('remove_obstacle', { x, y }), [send]);
  const failRobot = useCallback((robot_id: string) =>
    send('fail_robot', { robot_id }), [send]);
  const recoverRobot = useCallback((robot_id: string) =>
    send('recover_robot', { robot_id }), [send]);
  const runBenchmark = useCallback((scenario?: string) =>
    send('run_benchmark', { scenario: scenario || '10_BENCHMARK' }), [send]);
  const injectLatency = useCallback((value: number) => send('inject_latency', { value }), [send]);
  const dropPackets = useCallback((value: number) => send('drop_packets', { value }), [send]);
  const demoMode = useCallback(() => send('demo_mode'), [send]);

  return {
    state,
    connected,
    benchmark,
    scenarios,
    play, pause, step, reset,
    setSpeed, loadScenario,
    injectObstacle, removeObstacle,
    failRobot, recoverRobot,
    runBenchmark, demoMode,
    injectLatency, dropPackets,
  };
}
