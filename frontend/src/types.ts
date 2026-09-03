export type ClickMode = 'OBSTACLE' | 'ROBOT';

export interface Position {
  x: number;
  y: number;
}

export interface RobotData {
  robot_id: string;
  position: [number, number];
  prev_position: [number, number];
  render_x: number;
  render_y: number;
  velocity: number;
  heading: number;
  battery: number;
  current_task: string | null;
  task_phase: string;
  destination: [number, number] | null;
  planned_path: [number, number][];
  status: string;
  priority: number;
  intent: string;
  waiting_for: string | null;
  waiting_time: number;
  total_waiting_time: number;
  distance_travelled: number;
  color: string;
  decision_reason: string;
  moving: boolean;
  move_progress: number;
  has_item: boolean;
  messages_sent: number;
  messages_received: number;
  hardware: {
    cpu: number;
    ram: number;
    latency: number;
    thermal: number;
  };
}


export interface TaskData {
  task_id: string;
  pickup: [number, number];
  dropoff: [number, number];
  priority: number;
  deadline: number | null;
  assigned_robot: string | null;
  status: string;
  creation_time: number;
  start_time: number | null;
  completion_time: number | null;
}

export interface EventData {
  tick: number;
  event_type: string;
  robot_id: string | null;
  description: string;
  data: Record<string, any>;
}

export interface MetricsData {
  total_task_completion_time: number;
  average_task_completion_time: number;
  throughput: number;
  total_waiting_time: number;
  average_waiting_time: number;
  num_conflicts: number;
  conflicts_resolved: number;
  collisions: number;
  deadlocks_detected: number;
  deadlock_recoveries: number;
  reroutes: number;
  total_distance: number;
  task_reassignments: number;
  unavailable_robots: number;
  communication_events: number;
  reservation_conflicts: number;
  tasks_completed: number;
  tasks_total: number;
  near_collisions: number;
  min_separation: number | null;
}

export interface WarehouseData {
  width: number;
  height: number;
  grid: string[][];
  locations: {
    pickups: [number, number][];
    dropoffs: [number, number][];
    charging_stations: [number, number][];
    staging_areas: [number, number][];
    intersections: [number, number][];
  };
  blocked_aisles: string[];
  dynamic_obstacles: [number, number][];
}

export interface CommEdge {
  from: string;
  to: string;
  type: string;
  tick: number;
  count?: number;
}

export interface CommSummary {
  from: string;
  to: string;
  total: number;
  by_type: Record<string, number>;
}

export interface SimulationState {
  tick: number;
  running: boolean;
  speed: number;
  baseline_mode: boolean;
  scenario: string | null;
  scenario_name: string | null;
  robots: Record<string, RobotData>;
  tasks: TaskData[];
  warehouse: WarehouseData;
  metrics: MetricsData;
  events: EventData[];
  comm_graph: CommEdge[];
  comm_summary: CommSummary[];
}

export interface BenchmarkResult {
  mode: string;
  scenario_id: string;
  seed: number;
  ticks: number;
  tasks_completed: number;
  tasks_total: number;
  total_completion_time: number;
  avg_completion_time: number;
  total_waiting_time: number;
  avg_waiting_time: number;
  collisions: number;
  deadlocks: number;
  deadlock_recoveries: number;
  reroutes: number;
  conflicts: number;
  conflicts_resolved: number;
  total_distance: number;
  task_reassignments: number;
  communication_events: number;
  wall_time_ms: number;
}

export interface BenchmarkComparison {
  scenario_id: string;
  baseline: BenchmarkResult | null;
  distributed: BenchmarkResult | null;
  improvement_pct: number;
  waiting_time_reduction_pct: number;
  collision_baseline: number;
  collision_distributed: number;
}

export interface ScenarioInfo {
  id: string;
  name: string;
  description: string;
  robots: number;
  tasks: number;
}
