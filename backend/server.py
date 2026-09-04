from __future__ import annotations

import asyncio
import json
import os
import io
import random
import traceback
from typing import List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import SimulationEngine
from models import Message, MessageType, Position, RobotStatus, Task
from scenarios import get_scenario, list_scenarios
from benchmark import run_benchmark


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GLOBALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

engine = SimulationEngine()
clients: Set[WebSocket] = set()
_sim_task: Optional[asyncio.Task] = None
_benchmark_result: Optional[dict] = None

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

@app.on_event("startup")
async def on_startup():
    global _sim_task
    # Load default scenario
    cfg = get_scenario("01_OPEN_WAREHOUSE")
    if cfg:
        engine.load_scenario(cfg)
    # Start simulation loop
    _sim_task = asyncio.create_task(simulation_loop())


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
        engine.fail_robot(robot_id)
        return {"status": "success", "robot_id": robot_id}
    return {"status": "error", "message": "Robot not found"}


@app.post("/api/recover_robot/{robot_id}")
def api_recover_robot(robot_id: str):
    if robot_id in engine.robots:
        engine.recover_robot(robot_id)
        return {"status": "success", "robot_id": robot_id}
    return {"status": "error", "message": "Robot not found"}


@app.get("/api/comm_graph")
def api_comm_graph():
    return {
        "recent_edges": engine.message_bus.get_comm_graph(
            recent_ticks=20, current_tick=engine.tick
        ),
        "summary": engine.message_bus.get_comm_summary(),
    }

class ObstacleRequest(BaseModel):
    x: int
    y: int

@app.post("/api/add_obstacle")
def api_add_obstacle(req: ObstacleRequest):
    pos = Position(req.x, req.y)
    engine.warehouse.add_obstacle(pos)
    engine._log_event("SYSTEM", None, f"Dynamic obstacle added at ({req.x}, {req.y})")
    
    # Alert all robots
    engine.message_bus.send(
        Message(
            type=MessageType.OBSTACLE_ALERT,
            sender_id="SYSTEM",
            timestamp=engine.tick,
            data={"cells": [(req.x, req.y)]},
        )
    )
    return {"status": "success"}


@app.post("/api/upload_blueprint_file")
async def api_upload_blueprint_file(file: UploadFile = File(...)):
    content = await file.read()
    
    try:
        from PIL import Image  # type: ignore
        import pymupdf as fitz  # type: ignore
    except ImportError:
        return {"status": "error", "message": "Pillow and PyMuPDF are required"}

    img = None
    filename = file.filename.lower() if file.filename else ""
    if filename.endswith(".pdf"):
        doc = fitz.open(stream=content, filetype="pdf")
        if doc.page_count > 0:
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
        doc.close()
    else:
        try:
            img = Image.open(io.BytesIO(content))
        except Exception:
            pass

    if not img:
        return {"status": "error", "message": "Could not process file"}

    img = img.convert("L")
    max_w, max_h = 100, 100
    w, h = img.size
    ratio = min(max_w/w, max_h/h)
    new_w, new_h = max(1, int(w * ratio)), max(1, int(h * ratio))
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    layout = []
    for y in range(new_h):
        row_str = ""
        for x in range(new_w):
            pixel = img.getpixel((x, y))
            if pixel < 128:
                row_str += "#"
            else:
                row_str += "."
        layout.append(row_str)

    engine.load_custom_layout(layout)
    await _broadcast_state(include_warehouse=True)
    return {"status": "success", "layout_size": f"{new_w}x{new_h}"}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SIMULATION LOOP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def simulation_loop():
    """Run the simulation and broadcast state to all WebSocket clients."""
    while True:
        if engine.running:
            try:
                await engine.step()
                state = engine.get_state(include_warehouse=False)
                state_json = json.dumps(state)
            except Exception:
                with open("traceback.txt", "w") as f:
                    traceback.print_exc(file=f)
                traceback.print_exc()
                engine.running = False
                await asyncio.sleep(1)
                continue

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
                    await _broadcast_state(include_warehouse=True)

            elif action == "play":
                engine.running = True
                await _broadcast_state()

            elif action == "pause":
                engine.running = False
                await _broadcast_state()

            elif action == "step":
                engine.running = False
                await engine.step()
                await _broadcast_state()

            elif action == "upload_blueprint":
                layout = cmd.get("layout", [])
                if layout:
                    engine.load_custom_layout(layout)
                    await _broadcast_state(include_warehouse=True)

            elif action == "reset":
                engine.reset()
                _benchmark_result = None
                await _broadcast_state(include_warehouse=True)

            elif action == "set_speed":
                engine.speed = float(cmd.get("speed", 1.0))

            elif action == "inject_obstacle":
                x, y = int(cmd.get("x", 0)), int(cmd.get("y", 0))
                engine.inject_obstacle(x, y)
                await _broadcast_state(include_warehouse=True)

            elif action == "remove_obstacle":
                x, y = int(cmd.get("x", 0)), int(cmd.get("y", 0))
                engine.remove_obstacle(x, y)
                await _broadcast_state(include_warehouse=True)

            elif action == "add_task":
                pickup = cmd.get("pickup", {"x": 0, "y": 0})
                dropoff = cmd.get("dropoff", {"x": 0, "y": 0})
                priority = int(cmd.get("priority", 1))
                task = Task(
                    task_id=f"TASK-M-{engine.tick}-{random.randint(1000, 9999)}",
                    pickup=Position(int(pickup["x"]), int(pickup["y"])),
                    dropoff=Position(int(dropoff["x"]), int(dropoff["y"])),
                    priority=priority
                )
                engine.task_pool.add_task(task)
                engine._log_event("SYSTEM", None, f"Manual task added: pickup {pickup}, dropoff {dropoff}")
                await _broadcast_state()

            elif action == "fail_robot":
                robot_id = cmd.get("robot_id", "")
                engine.fail_robot(robot_id)
                await _broadcast_state()

            elif action == "recover_robot":
                robot_id = cmd.get("robot_id", "")
                engine.recover_robot(robot_id)
                await _broadcast_state()

            elif action == "add_robot":
                x, y = int(cmd.get("x", 0)), int(cmd.get("y", 0))
                robot_id = engine.add_robot(x, y)
                if robot_id:
                    await _broadcast_state(include_warehouse=False)

            elif action == "remove_robot":
                robot_id = cmd.get("robot_id", "")
                engine.remove_robot(robot_id)
                await _broadcast_state(include_warehouse=False)

            elif action == "inject_latency":
                val = int(cmd.get("value", 1))
                engine.message_bus.base_latency_ticks = val
                await _broadcast_state()

            elif action == "drop_packets":
                val = float(cmd.get("value", 0.05))
                engine.message_bus.packet_drop_prob = val
                await _broadcast_state()

            elif action == "add_dead_zone":
                x1 = int(cmd.get("x1", 0))
                y1 = int(cmd.get("y1", 0))
                x2 = int(cmd.get("x2", 0))
                y2 = int(cmd.get("y2", 0))
                engine.add_dead_zone(x1, y1, x2, y2)
                await _broadcast_state()

            elif action == "remove_dead_zone":
                x1 = int(cmd.get("x1", 0))
                y1 = int(cmd.get("y1", 0))
                x2 = int(cmd.get("x2", 0))
                y2 = int(cmd.get("y2", 0))
                engine.remove_dead_zone(x1, y1, x2, y2)
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
                    await _broadcast_state(include_warehouse=True)

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        clients.discard(ws)


async def _broadcast_state(include_warehouse: bool = False):
    """Send current state to all connected clients."""
    state = json.dumps(engine.get_state(include_warehouse=include_warehouse))
    dead = []
    for ws in clients:
        try:
            await ws.send_text(state)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


# ── Run directly ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
