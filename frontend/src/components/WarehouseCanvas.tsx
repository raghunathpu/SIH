import { useRef, useEffect, useState, useCallback } from 'react';
import type { SimulationState, RobotData } from '../types';

/* ────────────────────────────────────────────────────────
 *  CELL COLOURS
 * ──────────────────────────────────────────────────────── */
const CELL_COLORS: Record<string, string> = {
  OPEN:     '#0b0c10',
  RACK:     '#1c1f26',
  PICKUP:   'rgba(16, 185, 129, 0.1)',
  DROPOFF:  'rgba(139, 92, 246, 0.1)',
  CHARGING: 'rgba(245, 158, 11, 0.1)',
  STAGING:  'rgba(59, 130, 246, 0.1)',
  OBSTACLE: 'rgba(239, 68, 68, 0.2)',
};

const CELL_BORDER = 'rgba(255, 255, 255, 0.03)';

/* ────────────────────────────────────────────────────────
 *  STATUS → INDICATOR COLOUR
 * ──────────────────────────────────────────────────────── */
const STATUS_COLOR: Record<string, string> = {
  IDLE:                 '#a0a6b8',
  MOVING:               '#10b981',
  APPROACHING_CONFLICT: '#f59e0b',
  NEGOTIATING:          '#f59e0b',
  WAITING:              '#ef4444',
  REROUTING:            '#3b82f6',
  PICKING:              '#8b5cf6',
  DROPPING:             '#8b5cf6',
  CHARGING:             '#f59e0b',
  BLOCKED:              '#ef4444',
  RECOVERY:             '#ec4899',
  UNAVAILABLE:          '#4b5563',
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
  
  // View transform state for pan/zoom
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

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

  // Pan and Zoom handlers
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const scaleAdjust = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform(prev => ({
      ...prev,
      scale: Math.max(0.5, Math.min(3, prev.scale * scaleAdjust))
    }));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y });
  }, [transform]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (isDragging) {
      setTransform(prev => ({
        ...prev,
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      }));
    }
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  // Canvas click handler (translated through zoom/pan)
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!state?.warehouse || !canvasRef.current) return;
    if (isDragging) return; // Don't trigger click on drag end
    
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = (e.clientX - rect.left - transform.x) / transform.scale;
    const my = (e.clientY - rect.top - transform.y) / transform.scale;
    
    const wh = state.warehouse;
    // Calculate base cell size before scale
    const rawCellW = size.w / wh.width;
    const rawCellH = size.h / wh.height;
    const cellSize = Math.min(rawCellW, rawCellH);
    const offsetX = (size.w - (wh.width * cellSize)) / 2;
    const offsetY = (size.h - (wh.height * cellSize)) / 2;
    
    // Adjust mouse coordinates by the centering offset
    const adjustedMx = mx - offsetX;
    const adjustedMy = my - offsetY;

    const gx = Math.floor(adjustedMx / cellSize);
    const gy = Math.floor(adjustedMy / cellSize);

    // Check if a robot is near this cell
    const robots = Object.values(state.robots);
    const clicked = robots.find(r =>
      Math.abs(r.render_x - gx) < 0.8 && Math.abs(r.render_y - gy) < 0.8
    );
    if (clicked) {
      onSelectRobot(clicked.robot_id);
    } else if (onCellClick && gx >= 0 && gx < wh.width && gy >= 0 && gy < wh.height) {
      onCellClick(gx, gy);
    } else {
      onSelectRobot(null);
    }
  }, [state, size, transform, isDragging, onSelectRobot, onCellClick]);

  // Render loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !state?.warehouse) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const draw = () => {
      const wh = state.warehouse;
      const robots = Object.values(state.robots);
      const rawCellW = size.w / wh.width;
      const rawCellH = size.h / wh.height;
      const cellSize = Math.min(rawCellW, rawCellH);
      const baseCellW = cellSize;
      const baseCellH = cellSize;
      const offsetX = (size.w - (wh.width * cellSize)) / 2;
      const offsetY = (size.h - (wh.height * cellSize)) / 2;

      ctx.clearRect(0, 0, size.w, size.h);
      
      // Apply transform
      ctx.save();
      ctx.translate(transform.x + offsetX, transform.y + offsetY);
      ctx.scale(transform.scale, transform.scale);

      // ── Grid Background ──
      for (let y = 0; y < wh.height; y++) {
        for (let x = 0; x < wh.width; x++) {
          const cellType = wh.grid[y]?.[x] || 'OPEN';
          ctx.fillStyle = CELL_COLORS[cellType] || CELL_COLORS.OPEN;
          ctx.fillRect(x * baseCellW, y * baseCellH, baseCellW, baseCellH);
          ctx.strokeStyle = CELL_BORDER;
          ctx.lineWidth = 1;
          ctx.strokeRect(x * baseCellW, y * baseCellH, baseCellW, baseCellH);
        }
      }

      // ── Location markers ──
      const locs = wh.locations;
      drawMarkers(ctx, locs.pickups, '#10b981', 'P', baseCellW, baseCellH);
      drawMarkers(ctx, locs.dropoffs, '#8b5cf6', 'D', baseCellW, baseCellH);
      drawMarkers(ctx, locs.charging_stations, '#f59e0b', '⚡', baseCellW, baseCellH);
      drawMarkers(ctx, locs.staging_areas, '#3b82f6', 'S', baseCellW, baseCellH);

      // ── Robot paths ──
      for (const r of robots) {
        if (r.status === 'UNAVAILABLE') continue;
        drawPath(ctx, r, baseCellW, baseCellH, r.robot_id === selectedRobot);
      }

      // ── Conflict zones (Glowing Pulse) ──
      const time = Date.now() / 1000;
      for (const r of robots) {
        if (r.waiting_for && (r.status === 'WAITING' || r.status === 'NEGOTIATING' || r.status === 'APPROACHING_CONFLICT')) {
          const cx = r.render_x * baseCellW + baseCellW / 2;
          const cy = r.render_y * baseCellH + baseCellH / 2;
          
          const pulse = (Math.sin(time * 5) + 1) / 2; // 0 to 1
          
          ctx.beginPath();
          ctx.arc(cx, cy, baseCellW * (0.6 + pulse * 0.4), 0, Math.PI * 2);
          ctx.fillStyle = `rgba(239, 68, 68, ${0.1 * (1 - pulse)})`;
          ctx.fill();
          ctx.strokeStyle = `rgba(239, 68, 68, ${0.3 * (1 - pulse)})`;
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }

      // ── Robots ──
      for (const r of robots) {
        drawRobot(ctx, r, baseCellW, baseCellH, r.robot_id === selectedRobot);
      }

      ctx.restore();
      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [state, size, transform, selectedRobot]);

  return (
    <div 
      ref={containerRef} 
      style={{ width: '100%', height: '100%', overflow: 'hidden', position: 'relative' }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      <canvas
        ref={canvasRef}
        width={size.w}
        height={size.h}
        onClick={handleClick}
        style={{ display: 'block', cursor: isDragging ? 'grabbing' : 'crosshair' }}
      />
      <div style={{ position: 'absolute', bottom: 16, right: 16, display: 'flex', gap: '0.5rem', zIndex: 10 }}>
        <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem' }} onClick={() => setTransform(t => ({...t, scale: Math.min(3, t.scale * 1.2)}))}>+</button>
        <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem' }} onClick={() => setTransform({ x: 0, y: 0, scale: 1 })}>Reset</button>
        <button className="btn btn-secondary" style={{ padding: '0.25rem 0.5rem' }} onClick={() => setTransform(t => ({...t, scale: Math.max(0.5, t.scale / 1.2)}))}>-</button>
      </div>
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
  ctx.font = `bold ${Math.max(10, cellW * 0.4)}px 'JetBrains Mono', monospace`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  for (const [x, y] of positions) {
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
  
  // Neon glow effect for selected path
  if (selected) {
    ctx.shadowColor = robot.color;
    ctx.shadowBlur = 8;
  }
  
  ctx.strokeStyle = robot.color + (selected ? 'ff' : '44');
  ctx.lineWidth = selected ? 3 : 1.5;
  
  // Animate dashed line moving forward
  const time = Date.now() / 50;
  ctx.setLineDash(selected ? [8, 4] : [4, 4]);
  ctx.lineDashOffset = -time;
  ctx.stroke();
  
  ctx.setLineDash([]);
  ctx.shadowBlur = 0;

  // Destination marker
  if (robot.destination) {
    const [dx, dy] = robot.destination;
    ctx.beginPath();
    ctx.arc(dx * cellW + cellW / 2, dy * cellH + cellH / 2, cellW * 0.3, 0, Math.PI * 2);
    ctx.fillStyle = robot.color + '33';
    ctx.fill();
    ctx.strokeStyle = robot.color;
    ctx.lineWidth = 2;
    ctx.stroke();
  }
}

function drawHexagon(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number) {
  ctx.beginPath();
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 3) * i - Math.PI / 6;
    const hx = x + radius * Math.cos(angle);
    const hy = y + radius * Math.sin(angle);
    if (i === 0) ctx.moveTo(hx, hy);
    else ctx.lineTo(hx, hy);
  }
  ctx.closePath();
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
  const radius = Math.min(cellW, cellH) * 0.4;
  const headingRad = (robot.heading * Math.PI) / 180;

  if (robot.status === 'UNAVAILABLE') {
    // Grey out
    drawHexagon(ctx, cx, cy, radius);
    ctx.fillStyle = '#1c1f26';
    ctx.fill();
    ctx.strokeStyle = '#4b5563';
    ctx.lineWidth = 1;
    ctx.stroke();
    // X mark
    ctx.beginPath();
    const s = radius * 0.5;
    ctx.moveTo(cx - s, cy - s); ctx.lineTo(cx + s, cy + s);
    ctx.moveTo(cx + s, cy - s); ctx.lineTo(cx - s, cy + s);
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 2;
    ctx.stroke();
    return;
  }

  // Selection ring
  if (selected) {
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 6, 0, Math.PI * 2);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  const statusCol = STATUS_COLOR[robot.status] || '#a0a6b8';

  // Body Glow
  ctx.shadowColor = robot.status === 'WAITING' || robot.status === 'NEGOTIATING' ? statusCol : robot.color;
  ctx.shadowBlur = 15;

  // Body (Hexagon instead of circle for tech look)
  drawHexagon(ctx, cx, cy, radius);
  ctx.fillStyle = robot.color;
  ctx.fill();
  
  ctx.shadowBlur = 0;

  // Status ring inside
  drawHexagon(ctx, cx, cy, radius * 0.7);
  ctx.strokeStyle = statusCol;
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Heading indicator
  const hx = cx + Math.cos(headingRad) * radius * 1.1;
  const hy = cy + Math.sin(headingRad) * radius * 1.1;
  ctx.beginPath();
  ctx.arc(hx, hy, radius * 0.25, 0, Math.PI * 2);
  ctx.fillStyle = '#fff';
  ctx.fill();
  
  // Has Item Indicator
  if (robot.has_item) {
     ctx.beginPath();
     ctx.arc(cx, cy, radius * 0.4, 0, Math.PI * 2);
     ctx.fillStyle = '#ffffff';
     ctx.fill();
  } else {
      // Label
      ctx.font = `bold ${Math.max(9, radius * 0.7)}px 'JetBrains Mono', monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#0b0c10';
      const label = robot.robot_id.replace('AMR-', '');
      ctx.fillText(label, cx, cy);
  }
}
