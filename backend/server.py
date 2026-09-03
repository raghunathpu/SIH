"""
FleetMind — FastAPI Server

HTTP REST + WebSocket server for the fleet dashboard.

WebSocket protocol:
  Server → Client (per tick):   full simulation state JSON
  Client → Server (commands):   JSON action messages

REST endpoints:
  GET  /api/scenarios          list available scenarios
  GET  /api/state              current state snapshot
  POST /api/benchmark          run benchmark and return results
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Dict, List, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from engine import SimulationEngine
from scenarios import get_scenario, list_scenarios, SCENARIOS
from benchmark import run_benchmark


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  APP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

app = FastAPI(title="FleetMind", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = SimulationEngine()
clients: Set[WebSocket] = set()
_sim_task: asyncio.Task | None = None
_benchmark_result: dict | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REST ENDPOINTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/api/scenarios")
def api_scenarios():
    return list_scenarios()


@app.get("/api/state")
def api_state():
    return engine.get_state()


@app.get("/api/benchmark_result")
def api_benchmark_result():
    return _benchmark_result or {}


class BenchmarkRequest(BaseModel):
    scenario: str = "10_BENCHMARK"


@app.post("/api/benchmark")
def api_benchmark(req: BenchmarkRequest):
    global _benchmark_result
    result = run_benchmark(req.scenario)
    _benchmark_result = result.to_dict()
    return _benchmark_result

@app.post("/api/fail_robot/{robot_id}")
def api_fail_robot(robot_id: str):
    if robot_id in engine.robots:
        robot = engine.robots[robot_id]
        from models import RobotStatus
        robot.status = RobotStatus.UNAVAILABLE
        robot.velocity = 0.0
        robot.moving = False
        robot._log_event(engine.tick, "FAILURE", "Simulated hardware failure")
        return {"status": "success", "robot_id": robot_id}
    return {"status": "error", "message": "Robot not found"}

class ObstacleRequest(BaseModel):
    x: int
    y: int

@app.post("/api/add_obstacle")
def api_add_obstacle(req: ObstacleRequest):
    from models import Position
    pos = Position(req.x, req.y)
    engine.warehouse.add_obstacle(pos)
    engine._log_event("SYSTEM", None, f"Dynamic obstacle added at ({req.x}, {req.y})")
    
    # Alert all robots
    from models import Message, MessageType
    engine.message_bus.send(
        Message(
            type=MessageType.OBSTACLE_ALERT,
            sender_id="SYSTEM",
            timestamp=engine.tick,
            data={"cells": [(req.x, req.y)]},
        )
    )
    return {"status": "success"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIMULATION LOOP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def simulation_loop():
    """Run the simulation and broadcast state to all WebSocket clients."""
    while True:
        if engine.running:
            engine.step()
            state = engine.get_state()
            state_json = json.dumps(state)

            # Broadcast to all connected clients
            dead: List[WebSocket] = []
            for ws in clients:
                try:
                    await ws.send_text(state_json)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                clients.discard(ws)

            # Tick rate based on speed
            delay = 0.05 / max(0.1, engine.speed)
            await asyncio.sleep(delay)
        else:
            await asyncio.sleep(0.1)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WEBSOCKET
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _sim_task, _benchmark_result

    await ws.accept()
    clients.add(ws)

    # Send initial state
    try:
        await ws.send_text(json.dumps(engine.get_state()))
    except Exception:
        pass

    try:
        while True:
            raw = await ws.receive_text()
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = cmd.get("action", "")

            if action == "load_scenario":
                scenario_id = cmd.get("scenario", "01_OPEN_WAREHOUSE")
                baseline = cmd.get("baseline", False)
                cfg = get_scenario(scenario_id)
                if cfg:
                    engine.load_scenario(cfg, baseline=baseline)
                    await _broadcast_state()

            elif action == "play":
                engine.running = True
                await _broadcast_state()

            elif action == "pause":
                engine.running = False
                await _broadcast_state()

            elif action == "step":
                engine.running = False
                engine.step()
                await _broadcast_state()

            elif action == "reset":
                engine.reset()
                _benchmark_result = None
                await _broadcast_state()

            elif action == "set_speed":
                engine.speed = float(cmd.get("speed", 1.0))

            elif action == "inject_obstacle":
                x, y = cmd.get("x", 0), cmd.get("y", 0)
                engine.inject_obstacle(x, y)
                await _broadcast_state()

            elif action == "remove_obstacle":
                x, y = cmd.get("x", 0), cmd.get("y", 0)
                engine.remove_obstacle(x, y)
                await _broadcast_state()

            elif action == "fail_robot":
                robot_id = cmd.get("robot_id", "")
                engine.fail_robot(robot_id)
                await _broadcast_state()

            elif action == "recover_robot":
                robot_id = cmd.get("robot_id", "")
                engine.recover_robot(robot_id)
                await _broadcast_state()

            elif action == "run_benchmark":
                scenario_id = cmd.get("scenario", "10_BENCHMARK")
                # Run benchmark in a separate thread to prevent blocking the event loop
                result = await asyncio.to_thread(run_benchmark, scenario_id)
                _benchmark_result = result.to_dict()
                await ws.send_text(json.dumps({
                    "type": "benchmark_result",
                    "data": _benchmark_result,
                }))

            elif action == "demo_mode":
                cfg = get_scenario("DEMO_MODE")
                if cfg:
                    engine.load_scenario(cfg)
                    engine.running = True
                    await _broadcast_state()

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        clients.discard(ws)


async def _broadcast_state():
    """Send current state to all connected clients."""
    state = json.dumps(engine.get_state())
    dead = []
    for ws in clients:
        try:
            await ws.send_text(state)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STARTUP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.on_event("startup")
async def on_startup():
    global _sim_task
    # Load default scenario
    cfg = get_scenario("01_OPEN_WAREHOUSE")
    if cfg:
        engine.load_scenario(cfg)
    # Start simulation loop
    _sim_task = asyncio.create_task(simulation_loop())


# ── Run directly ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
