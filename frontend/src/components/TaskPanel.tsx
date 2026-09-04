import React, { useState } from 'react';
import type { SimulationState } from '../types';

interface TaskPanelProps {
  onAddTask: (pickup: {x: number, y: number}, dropoff: {x: number, y: number}, priority: number) => void;
  state: SimulationState | null;
}

export const TaskPanel: React.FC<TaskPanelProps> = ({ onAddTask, state }) => {
  const [pickupX, setPickupX] = useState<string>('2');
  const [pickupY, setPickupY] = useState<string>('2');
  const [dropoffX, setDropoffX] = useState<string>('28');
  const [dropoffY, setDropoffY] = useState<string>('18');
  const [priority, setPriority] = useState<string>('1');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAddTask(
      { x: parseInt(pickupX, 10), y: parseInt(pickupY, 10) },
      { x: parseInt(dropoffX, 10), y: parseInt(dropoffY, 10) },
      parseInt(priority, 10)
    );
  };

  const tasks = state?.tasks || [];
  // Sort tasks: pending first, then in-progress, then completed. Or just reverse chronological.
  const displayTasks = [...tasks].reverse().slice(0, 50); // last 50 tasks for performance

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'PENDING': return 'text-slate-400 bg-slate-500/20';
      case 'IN_PROGRESS': return 'text-amber-400 bg-amber-500/20';
      case 'COMPLETED': return 'text-emerald-400 bg-emerald-500/20';
      case 'CANCELLED': 
      case 'FAILED': return 'text-rose-400 bg-rose-500/20';
      default: return 'text-slate-400 bg-slate-500/20';
    }
  };

  return (
    <div className="card mt-4" style={{ display: 'flex', flexDirection: 'column', maxHeight: '500px' }}>
      <div className="card-header">
        <span>Task Queue & Dispatch</span>
      </div>
      
      {/* Dispatch Form */}
      <div className="card-body" style={{ padding: '0.75rem', borderBottom: '1px solid var(--border)' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary block">Pickup X</label>
              <input type="number" value={pickupX} onChange={e => setPickupX(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-xs text-white" />
            </div>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary block">Pickup Y</label>
              <input type="number" value={pickupY} onChange={e => setPickupY(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-xs text-white" />
            </div>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary block">Dropoff X</label>
              <input type="number" value={dropoffX} onChange={e => setDropoffX(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-xs text-white" />
            </div>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary block">Dropoff Y</label>
              <input type="number" value={dropoffY} onChange={e => setDropoffY(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-xs text-white" />
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end' }}>
             <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary block">Priority</label>
              <select value={priority} onChange={e => setPriority(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-xs text-white">
                <option value="1">Normal (1)</option>
                <option value="5">High (5)</option>
                <option value="10">Urgent (10)</option>
              </select>
            </div>
            <button type="submit" className="bg-blue-500 hover:bg-blue-600 text-white rounded px-3 py-1 text-xs font-bold transition-colors" style={{ height: '26px' }}>
              Dispatch
            </button>
          </div>
        </form>
      </div>

      {/* Task Queue List */}
      <div className="card-body" style={{ flex: 1, overflowY: 'auto', padding: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {displayTasks.length === 0 ? (
          <div className="text-center text-tertiary text-xs mt-2">No active tasks</div>
        ) : (
          displayTasks.map(t => (
            <div key={t.task_id} className="bg-surface-elevated rounded p-2 text-xs" style={{ borderLeft: `3px solid ${t.assigned_robot ? '#3b82f6' : '#64748b'}` }}>
              <div className="flex justify-between items-center mb-1">
                <span className="font-bold text-white">{t.task_id}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getStatusColor(t.status)}`}>
                  {t.status}
                </span>
              </div>
              <div className="flex justify-between items-center text-secondary">
                <span>P:({t.pickup[0]},{t.pickup[1]}) ➔ D:({t.dropoff[0]},{t.dropoff[1]})</span>
                {t.assigned_robot ? (
                  <span className="text-blue-300 font-mono bg-blue-500/10 px-1 rounded">🤖 {t.assigned_robot}</span>
                ) : (
                  <span className="text-slate-400 font-mono">Unassigned</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
