# FleetMind: Edge-AI Based Distributed Fleet Coordination for AMRs

FleetMind is a decentralized coordination and collision-avoidance framework for a multi-robot fleet of Autonomous Mobile Robots (AMRs) operating in a dynamic warehouse environment. It shifts path-planning from a centralized cloud server to a decentralized edge-computing solution where robots communicate via a peer-to-peer network to negotiate priority, resolve conflicts, and allocate tasks.

This repository includes a full-stack simulation environment:
- **Backend**: A Python/FastAPI simulation engine that runs the peer-to-peer logic, physics, path planning, and conflict resolution.
- **Frontend**: A React/Vite web dashboard for monitoring the fleet, injecting dynamic obstacles or network faults, and benchmarking performance.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**

## Installation & Setup

### 1. Backend Setup

The backend handles the simulation engine, AMRs agents, and WebSocket communication.

1. Navigate to the `backend` directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment (recommended):
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the backend server:
   ```bash
   python server.py
   ```
   The backend will now be running on `http://localhost:8000`.

### 2. Frontend Setup

The frontend provides the Fleet Dashboard and visualization tools.

1. Open a new terminal and navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```
2. Install the Node modules:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The frontend dashboard will now be accessible at `http://localhost:5173`.

## How to Use the Application

Once both servers are running, open your browser to `http://localhost:5173`.

### Main Controls
- **Scenarios**: Use the top-left dropdown to load different warehouse situations, such as "Cross Traffic", "Choke Point", or "Aisle Blockage".
- **Algorithms**: Toggle between **Distributed** (edge-AI peer-to-peer logic) and **Baseline** (traditional stop-and-wait central planning) to see how the AMRs react differently.
- **Playback**: Use the Play (▶️), Pause (⏸️), and Step (⏭️) buttons to control the flow of time. You can also adjust the simulation speed using the slider. Spacebar quickly toggles play/pause.

### Monitoring & Dashboards
- **Grid View (Default)**: Watch the AMRs navigate the warehouse. `P` represents Pickup zones, and `D` represents Dropoff zones.
- **Active Fleet**: The left sidebar shows all robots. Clicking on a robot opens its detailed telemetry panel on the right.
- **P2P Network Tab**: Visualizes the decentralized communication graph showing active message passing and topology between the robots.
- **Hardware Telemetry Tab**: Displays simulated edge hardware metrics (CPU, RAM, Thermal).

### Interacting with the Simulation
- **Inject Dynamic Obstacles**: Click on any empty cell in the Grid View to instantly spawn a blocked cell. The robots will detect it and try to find an alternative route.
- **Fault Injection**: Use the sliders in the bottom-left to introduce **Network Latency** or **Packet Loss**, simulating poor Wi-Fi conditions.
- **Simulate Hardware Failure**: Select a robot and click the "Simulate Hardware Failure" button in its detail panel to see the system automatically reassign its pending tasks to another available robot.

## Benchmarking

Click the **📊 Benchmark** button to automatically run the current scenario in the background for both Baseline and Distributed modes. A comparison report will be generated showing the reduction in overall task completion time and collisions.

---
*Developed for Problem Statement ID26123: Edge-AI Based Distributed Fleet Coordination for Autonomous Mobile Robots (AMRs) in Smart Warehouses.*
