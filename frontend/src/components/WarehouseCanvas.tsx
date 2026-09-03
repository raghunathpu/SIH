import { useRef, useEffect, useState, useCallback } from 'react';
import type { SimulationState, RobotData } from '../types';

/* ────────────────────────────────────────────────────────
 *  CELL COLOURS
 * ──────────────────────────────────────────────────────── */
const CELL_COLORS: Record<string, string> = {
  OPEN:     '#1a1d23',
  RACK:     '#2d3748',
  PICKUP:   '#1a3a2a',
  DROPOFF:  '#2a1a3a',
  CHARGING: '#3a2a1a',
  STAGING:  '#1a2a3a',
  OBSTACLE: '#4a1a1a',
};

const CELL_BORDER = '#252830';

/* ────────────────────────────────────────────────────────
 *  STATUS → INDICATOR COLOUR
 * ──────────────────────────────────────────────────────── */
const STATUS_COLOR: Record<string, string> = {
  IDLE:                 '#4a5568',
  MOVING:               '#48bb78',
  APPROACHING_CONFLICT: '#ed8936',
  NEGOTIATING:          '#ecc94b',
  WAITING:              '#fc8181',
  REROUTING:            '#63b3ed',
  PICKING:              '#9f7aea',
  DROPPING:             '#9f7aea',
  CHARGING:             '#fbd38d',
  BLOCKED:              '#f56565',
  RECOVERY:             '#ed64a6',
  UNAVAILABLE:          '#2d3748',
};

interface Props {
  state: SimulationState | null;
  selectedRobot: string | null;
  onSelectRobot: (id: string | null) => void;
  onCellClick?: (x: number, y: number) => void;
}

export default function WarehouseCanvas({ state, selectedRobot, onSelectRobot, onCellClick }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 540 });
  const animFrameRef = useRef<number>(0);

  // Responsive sizing
  useEffect(() => {
    const obs = new ResizeObserver(entries => {
      for (const e of entries) {
        const { width, height } = e.contentRect;
        setSize({ w: Math.floor(width), h: Math.floor(height) });
      }
    });
    if (containerRef.current) obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // Canvas click handler
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!state?.warehouse || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const wh = state.warehouse;
    const cellW = size.w / wh.width;
    const cellH = size.h / wh.height;
    const gx = Math.floor(mx / cellW);
    const gy = Math.floor(my / cellH);

    // Check if a robot is near this cell
    const robots = Object.values(state.robots);
    const clicked = robots.find(r =>
      Math.abs(r.render_x - gx) < 0.8 && Math.abs(r.render_y - gy) < 0.8
    );
    if (clicked) {
      onSelectRobot(clicked.robot_id);
    } else if (onCellClick) {
      onCellClick(gx, gy);
    } else {
      onSelectRobot(null);
    }
  }, [state, size, onSelectRobot, onCellClick]);

  // Render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !state?.warehouse) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const wh = state.warehouse;
      const robots = Object.values(state.robots);
      const cellW = size.w / wh.width;
      const cellH = size.h / wh.height;

      ctx.clearRect(0, 0, size.w, size.h);

      // ── Grid ──
      for (let y = 0; y < wh.height; y++) {
        for (let x = 0; x < wh.width; x++) {
          const cellType = wh.grid[y]?.[x] || 'OPEN';
          ctx.fillStyle = CELL_COLORS[cellType] || CELL_COLORS.OPEN;
          ctx.fillRect(x * cellW, y * cellH, cellW, cellH);
          ctx.strokeStyle = CELL_BORDER;
          ctx.lineWidth = 0.5;
          ctx.strokeRect(x * cellW, y * cellH, cellW, cellH);
        }
      }

      // ── Location markers ──
      const locs = wh.locations;
      drawMarkers(ctx, locs.pickups, '#48bb78', 'P', cellW, cellH);
      drawMarkers(ctx, locs.dropoffs, '#9f7aea', 'D', cellW, cellH);
      drawMarkers(ctx, locs.charging_stations, '#fbd38d', '⚡', cellW, cellH);
      drawMarkers(ctx, locs.staging_areas, '#63b3ed', 'S', cellW, cellH);

      // ── Robot paths ──
      for (const r of robots) {
        if (r.status === 'UNAVAILABLE') continue;
        drawPath(ctx, r, cellW, cellH, r.robot_id === selectedRobot);
      }

      // ── Conflict zones ──
      for (const r of robots) {
        if (r.waiting_for && (r.status === 'WAITING' || r.status === 'NEGOTIATING')) {
          const cx = r.render_x * cellW + cellW / 2;
          const cy = r.render_y * cellH + cellH / 2;
          ctx.beginPath();
          ctx.arc(cx, cy, cellW * 0.8, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(37, 40, 48, ${0.1})`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }

      // ── Robots ──
      for (const r of robots) {
        drawRobot(ctx, r, cellW, cellH, r.robot_id === selectedRobot);
      }

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [state, size, selectedRobot]);

  return (
    <div ref={containerRef} style={{ width: '100%', height: '100%', overflow: 'hidden' }}>
      <canvas
        ref={canvasRef}
        width={size.w}
        height={size.h}
        onClick={handleClick}
        style={{ display: 'block', cursor: 'crosshair' }}
      />
    </div>
  );
}

/* ────────────────────────────────────────────────────────
 *  DRAWING HELPERS
 * ──────────────────────────────────────────────────────── */

function drawMarkers(
  ctx: CanvasRenderingContext2D,
  positions: [number, number][],
  color: string,
  label: string,
  cellW: number,
  cellH: number,
) {
  ctx.font = `bold ${Math.max(8, cellW * 0.4)}px 'JetBrains Mono', monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (const [x, y] of positions) {
    ctx.fillStyle = color + '30';
    ctx.fillRect(x * cellW + 1, y * cellH + 1, cellW - 2, cellH - 2);
    ctx.fillStyle = color;
    ctx.fillText(label, x * cellW + cellW / 2, y * cellH + cellH / 2);
  }
}

function drawPath(
  ctx: CanvasRenderingContext2D,
  robot: RobotData,
  cellW: number,
  cellH: number,
  selected: boolean,
) {
  if (!robot.planned_path.length) return;

  ctx.beginPath();
  ctx.moveTo(robot.render_x * cellW + cellW / 2, robot.render_y * cellH + cellH / 2);
  for (const [px, py] of robot.planned_path) {
    ctx.lineTo(px * cellW + cellW / 2, py * cellH + cellH / 2);
  }
  ctx.strokeStyle = robot.color + (selected ? '99' : '44');
  ctx.lineWidth = selected ? 3 : 1.5;
  ctx.setLineDash(selected ? [] : [4, 4]);
  ctx.stroke();
  ctx.setLineDash([]);

  // Destination marker
  if (robot.destination) {
    const [dx, dy] = robot.destination;
    ctx.beginPath();
    ctx.arc(dx * cellW + cellW / 2, dy * cellH + cellH / 2, cellW * 0.3, 0, Math.PI * 2);
    ctx.strokeStyle = robot.color + '88';
    ctx.lineWidth = 2;
    ctx.setLineDash([3, 3]);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function drawRobot(
  ctx: CanvasRenderingContext2D,
  robot: RobotData,
  cellW: number,
  cellH: number,
  selected: boolean,
) {
  const cx = robot.render_x * cellW + cellW / 2;
  const cy = robot.render_y * cellH + cellH / 2;
  const radius = Math.min(cellW, cellH) * 0.35;
  const headingRad = (robot.heading * Math.PI) / 180;

  if (robot.status === 'UNAVAILABLE') {
    // Grey out
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = '#2d3748';
    ctx.fill();
    ctx.strokeStyle = '#4a5568';
    ctx.lineWidth = 1;
    ctx.stroke();
    // X mark
    ctx.beginPath();
    const s = radius * 0.5;
    ctx.moveTo(cx - s, cy - s); ctx.lineTo(cx + s, cy + s);
    ctx.moveTo(cx + s, cy - s); ctx.lineTo(cx - s, cy + s);
    ctx.strokeStyle = '#f56565';
    ctx.lineWidth = 2;
    ctx.stroke();
    return;
  }

  // Selection ring
  if (selected) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 4, 0, Math.PI * 2);
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Body
  ctx.beginPath();
  ctx.arc(cx, cy, radius, 0, Math.PI * 2);
  ctx.fillStyle = robot.color;
  ctx.fill();

  // Status ring
  const statusCol = STATUS_COLOR[robot.status] || '#4a5568';
  ctx.beginPath();
  ctx.arc(cx, cy, radius + 1.5, 0, Math.PI * 2);
  ctx.strokeStyle = statusCol;
  ctx.lineWidth = 2;
  ctx.stroke();

  // Heading indicator (triangle)
  const hx = cx + Math.cos(headingRad) * radius * 0.9;
  const hy = cy + Math.sin(headingRad) * radius * 0.9;
  ctx.beginPath();
  ctx.arc(hx, hy, radius * 0.25, 0, Math.PI * 2);
  ctx.fillStyle = '#fff';
  ctx.fill();

  // Label
  ctx.font = `bold ${Math.max(7, radius * 0.7)}px 'Inter', sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillStyle = '#000';
  const label = robot.robot_id.replace('AMR-', '');
  ctx.fillText(label, cx, cy);

  // Battery indicator (small bar below)
  const barW = radius * 1.4;
  const barH = 3;
  const barX = cx - barW / 2;
  const barY = cy + radius + 4;
  ctx.fillStyle = '#1a1d23';
  ctx.fillRect(barX, barY, barW, barH);
  const batColor = robot.battery > 50 ? '#48bb78' : robot.battery > 20 ? '#ecc94b' : '#f56565';
  ctx.fillStyle = batColor;
  ctx.fillRect(barX, barY, barW * (robot.battery / 100), barH);
}
