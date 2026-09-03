import React, { useEffect, useRef } from 'react';
import type { SimulationState } from '../types';

interface Props {
  state: SimulationState | null;
}

export const NetworkTopologyView: React.FC<Props> = ({ state }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !containerRef.current || !state) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle resize
    const resize = () => {
      if (containerRef.current) {
        canvas.width = containerRef.current.clientWidth;
        canvas.height = containerRef.current.clientHeight;
      }
    };
    resize();
    window.addEventListener('resize', resize);

    let animId: number;

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const robots = Object.values(state.robots);
      if (robots.length === 0) return;

      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const radius = Math.min(cx, cy) * 0.7;

      // Calculate node positions in a circle
      const nodes: Record<string, {x: number, y: number, color: string, active: boolean}> = {};
      robots.forEach((r, i) => {
        const angle = (i / robots.length) * Math.PI * 2 - Math.PI / 2;
        nodes[r.robot_id] = {
          x: cx + Math.cos(angle) * radius,
          y: cy + Math.sin(angle) * radius,
          color: r.color,
          active: r.status !== 'UNAVAILABLE'
        };
      });

      // Draw active edges from comm_graph (animated pulses)
      const currentTick = state.tick;
      if (state.comm_graph) {
        state.comm_graph.forEach(edge => {
          const from = nodes[edge.from];
          const to = nodes[edge.to];
          if (!from || !to) return;

          const age = currentTick - edge.tick;
          if (age > 20) return; // fade out

          const opacity = Math.max(0, 1 - age / 20);
          
          // Determine edge style by type
          let color = '#a0a6b8'; // default
          let dash = [];
          if (edge.type === 'HEARTBEAT') { color = '#3b82f6'; dash = [2, 4]; }
          if (edge.type.includes('TASK')) { color = '#10b981'; dash = [5, 5]; }
          if (edge.type === 'PRIORITY_CLAIM' || edge.type === 'WAIT_FOR') { color = '#f59e0b'; }
          if (edge.type.includes('DEADLOCK') || edge.type === 'OBSTACLE_ALERT') { color = '#ef4444'; }

          ctx.beginPath();
          ctx.moveTo(from.x, from.y);
          // Curve it slightly based on distance to center
          const cpx = (from.x + to.x) / 2 + (Math.random() - 0.5) * 20 * (1-opacity);
          const cpy = (from.y + to.y) / 2 + (Math.random() - 0.5) * 20 * (1-opacity);
          ctx.quadraticCurveTo(cpx, cpy, to.x, to.y);
          
          ctx.strokeStyle = `rgba(${hexToRgb(color)}, ${opacity * 0.8})`;
          ctx.lineWidth = 1.5;
          ctx.setLineDash(dash);
          ctx.stroke();

          // Draw an animated particle moving along the edge
          if (age < 5) {
             const t = age / 5; // 0 to 1
             const px = (1-t)*(1-t)*from.x + 2*(1-t)*t*cpx + t*t*to.x;
             const py = (1-t)*(1-t)*from.y + 2*(1-t)*t*cpy + t*t*to.y;
             ctx.beginPath();
             ctx.arc(px, py, 3, 0, Math.PI*2);
             ctx.fillStyle = color;
             ctx.fill();
             ctx.shadowColor = color;
             ctx.shadowBlur = 10;
          }
          ctx.shadowBlur = 0;
        });
      }

      ctx.setLineDash([]);

      // Draw nodes
      Object.entries(nodes).forEach(([id, n]) => {
        // Node halo
        if (n.active) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, 25, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(${hexToRgb(n.color)}, 0.1)`;
          ctx.fill();
        }

        // Node center
        ctx.beginPath();
        ctx.arc(n.x, n.y, 16, 0, Math.PI * 2);
        ctx.fillStyle = n.active ? n.color : '#2d3748';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Label
        ctx.font = 'bold 12px "JetBrains Mono"';
        ctx.fillStyle = '#fff';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(id.replace('AMR-', ''), n.x, n.y);
      });

      animId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animId);
    };
  }, [state]);

  // Helper to convert hex to rgb string "r, g, b"
  function hexToRgb(hex: string) {
    let r = 0, g = 0, b = 0;
    if (hex.length === 4) {
      r = parseInt(hex[1]+hex[1], 16);
      g = parseInt(hex[2]+hex[2], 16);
      b = parseInt(hex[3]+hex[3], 16);
    } else if (hex.length === 7) {
      r = parseInt(hex.substring(1,3), 16);
      g = parseInt(hex.substring(3,5), 16);
      b = parseInt(hex.substring(5,7), 16);
    }
    return `${r}, ${g}, ${b}`;
  }

  return (
    <div className="card h-full" style={{ height: '100%' }}>
      <div className="card-header">
        <h2 className="text-lg text-primary">Decentralized Communication Mesh</h2>
      </div>
      <div className="card-body relative" style={{ padding: 0 }} ref={containerRef}>
        <div style={{ position: 'absolute', top: 16, left: 16, background: 'var(--bg-surface-elevated)', padding: '8px 12px', borderRadius: '8px', fontSize: '0.75rem', border: '1px solid var(--border-color)', zIndex: 10 }}>
          <div className="font-bold mb-2">Legend</div>
          <div className="flex items-center gap-2 mb-1"><div className="w-3 h-0.5 bg-blue-500 border-dashed border-b-2"></div> Heartbeat</div>
          <div className="flex items-center gap-2 mb-1"><div className="w-3 h-0.5 bg-emerald-500"></div> Task Auction</div>
          <div className="flex items-center gap-2 mb-1"><div className="w-3 h-0.5 bg-amber-500"></div> Negotiation</div>
          <div className="flex items-center gap-2"><div className="w-3 h-0.5 bg-red-500"></div> Deadlock/Alert</div>
        </div>
        <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      </div>
    </div>
  );
};
