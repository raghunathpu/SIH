"""
FleetMind — Benchmark Runner

Runs the same scenario in BASELINE (stop-and-wait) mode and
DISTRIBUTED coordination mode, records metrics, and computes
the improvement percentage.

Formula:
  improvement_pct = ((baseline_time - distributed_time) / baseline_time) * 100

All results come from actual simulation execution.  Nothing is
hard-coded or fabricated.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from models import SimulationMetrics
from engine import SimulationEngine
from scenarios import ScenarioConfig, get_scenario


@dataclass
class BenchmarkResult:
    """Results of one benchmark run (baseline or distributed)."""
    mode: str                          # "BASELINE" or "DISTRIBUTED"
    scenario_id: str
    seed: int
    ticks: int = 0
    tasks_completed: int = 0
    tasks_total: int = 0
    total_completion_time: int = 0
    avg_completion_time: float = 0.0
    total_waiting_time: int = 0
    avg_waiting_time: float = 0.0
    collisions: int = 0
    deadlocks: int = 0
    deadlock_recoveries: int = 0
    reroutes: int = 0
    conflicts: int = 0
    conflicts_resolved: int = 0
    total_distance: float = 0.0
    task_reassignments: int = 0
    communication_events: int = 0
    wall_time_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "ticks": self.ticks,
            "tasks_completed": self.tasks_completed,
            "tasks_total": self.tasks_total,
            "total_completion_time": self.total_completion_time,
            "avg_completion_time": round(self.avg_completion_time, 1),
            "total_waiting_time": self.total_waiting_time,
            "avg_waiting_time": round(self.avg_waiting_time, 1),
            "collisions": self.collisions,
            "deadlocks": self.deadlocks,
            "deadlock_recoveries": self.deadlock_recoveries,
            "reroutes": self.reroutes,
            "conflicts": self.conflicts,
            "conflicts_resolved": self.conflicts_resolved,
            "total_distance": round(self.total_distance, 1),
            "task_reassignments": self.task_reassignments,
            "communication_events": self.communication_events,
            "wall_time_ms": round(self.wall_time_ms, 1),
        }


@dataclass
class BenchmarkComparison:
    """Side-by-side comparison of baseline vs distributed."""
    scenario_id: str
    baseline: Optional[BenchmarkResult] = None
    distributed: Optional[BenchmarkResult] = None
    improvement_pct: float = 0.0
    waiting_time_reduction_pct: float = 0.0
    collision_baseline: int = 0
    collision_distributed: int = 0

    def compute_improvement(self):
        if self.baseline and self.distributed:
            bt = self.baseline.total_completion_time
            dt = self.distributed.total_completion_time
            if bt > 0:
                self.improvement_pct = ((bt - dt) / bt) * 100
            else:
                self.improvement_pct = 0.0

            bw = self.baseline.total_waiting_time
            dw = self.distributed.total_waiting_time
            if bw > 0:
                self.waiting_time_reduction_pct = ((bw - dw) / bw) * 100
            else:
                self.waiting_time_reduction_pct = 0.0

            self.collision_baseline = self.baseline.collisions
            self.collision_distributed = self.distributed.collisions

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "distributed": self.distributed.to_dict() if self.distributed else None,
            "improvement_pct": round(self.improvement_pct, 1),
            "waiting_time_reduction_pct": round(self.waiting_time_reduction_pct, 1),
            "collision_baseline": self.collision_baseline,
            "collision_distributed": self.collision_distributed,
        }


def _run_scenario(
    cfg: ScenarioConfig,
    baseline: bool,
) -> BenchmarkResult:
    """
    Execute a scenario to completion and return metrics.
    """
    engine = SimulationEngine()
    engine.load_scenario(cfg, baseline=baseline)
    engine.running = True

    t0 = time.perf_counter()

    import asyncio
    async def run_sim():
        while engine.running:
            if not await engine.step():
                break
    
    asyncio.run(run_sim())

    wall_ms = (time.perf_counter() - t0) * 1000
    m = engine.metrics

    return BenchmarkResult(
        mode="BASELINE" if baseline else "DISTRIBUTED",
        scenario_id=cfg.scenario_id,
        seed=cfg.seed,
        ticks=engine.tick,
        tasks_completed=m.tasks_completed,
        tasks_total=m.tasks_total,
        total_completion_time=m.total_task_completion_time,
        avg_completion_time=m.average_task_completion_time,
        total_waiting_time=m.total_waiting_time,
        avg_waiting_time=m.average_waiting_time,
        collisions=m.collisions,
        deadlocks=m.deadlocks_detected,
        deadlock_recoveries=m.deadlock_recoveries,
        reroutes=m.reroutes,
        conflicts=m.num_conflicts,
        conflicts_resolved=m.conflicts_resolved,
        total_distance=m.total_distance,
        task_reassignments=m.task_reassignments,
        communication_events=m.communication_events,
        wall_time_ms=wall_ms,
    )


def run_benchmark(
    scenario_id: str = "10_BENCHMARK",
) -> BenchmarkComparison:
    """
    Run the full benchmark: baseline then distributed, same scenario.

    Returns a BenchmarkComparison with computed improvement %.
    """
    cfg = get_scenario(scenario_id)
    if cfg is None:
        raise ValueError(f"Unknown scenario: {scenario_id}")

    # ── Run BASELINE ─────────────────────────────────────
    baseline_result = _run_scenario(cfg, baseline=True)

    # ── Run DISTRIBUTED ──────────────────────────────────
    distributed_result = _run_scenario(cfg, baseline=False)

    # ── Compare ──────────────────────────────────────────
    comparison = BenchmarkComparison(
        scenario_id=scenario_id,
        baseline=baseline_result,
        distributed=distributed_result,
    )
    comparison.compute_improvement()

    return comparison


# ── CLI entry point ──────────────────────────────────────

if __name__ == "__main__":
    import sys

    scenario = sys.argv[1] if len(sys.argv) > 1 else "10_BENCHMARK"
    print(f"Running benchmark: {scenario}")
    print("=" * 60)

    result = run_benchmark(scenario)

    print(f"\nBASELINE:")
    print(f"  Ticks: {result.baseline.ticks}")
    print(f"  Tasks completed: {result.baseline.tasks_completed}/{result.baseline.tasks_total}")
    print(f"  Total completion time: {result.baseline.total_completion_time}")
    print(f"  Total waiting time: {result.baseline.total_waiting_time}")
    print(f"  Collisions: {result.baseline.collisions}")
    print(f"  Deadlocks: {result.baseline.deadlocks}")

    print(f"\nDISTRIBUTED:")
    print(f"  Ticks: {result.distributed.ticks}")
    print(f"  Tasks completed: {result.distributed.tasks_completed}/{result.distributed.tasks_total}")
    print(f"  Total completion time: {result.distributed.total_completion_time}")
    print(f"  Total waiting time: {result.distributed.total_waiting_time}")
    print(f"  Collisions: {result.distributed.collisions}")
    print(f"  Reroutes: {result.distributed.reroutes}")

    print(f"\nIMPROVEMENT:")
    print(f"  Task completion time: {result.improvement_pct:.1f}%")
    print(f"  Waiting time reduction: {result.waiting_time_reduction_pct:.1f}%")
    print(f"  Collisions: {result.collision_baseline} -> {result.collision_distributed}")
    print("=" * 60)

    # Save raw JSON
    with open("benchmark_results.json", "w") as f:
        json.dump(result.to_dict(), f, indent=2)
    print("Results saved to benchmark_results.json")
