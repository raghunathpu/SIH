import React, { useState } from 'react';

interface TaskPanelProps {
  onAddTask: (pickup: {x: number, y: number}, dropoff: {x: number, y: number}, priority: number) => void;
}

export const TaskPanel: React.FC<TaskPanelProps> = ({ onAddTask }) => {
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

  return (
    <div className="card mt-4">
      <div className="card-header">
        <span>Dispatch Task</span>
      </div>
      <div className="card-body" style={{ padding: '0.75rem' }}>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary mb-1 block">Pickup X</label>
              <input type="number" value={pickupX} onChange={e => setPickupX(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-sm text-white" />
            </div>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary mb-1 block">Pickup Y</label>
              <input type="number" value={pickupY} onChange={e => setPickupY(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-sm text-white" />
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary mb-1 block">Dropoff X</label>
              <input type="number" value={dropoffX} onChange={e => setDropoffX(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-sm text-white" />
            </div>
            <div style={{ flex: 1 }}>
              <label className="text-xs text-secondary mb-1 block">Dropoff Y</label>
              <input type="number" value={dropoffY} onChange={e => setDropoffY(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-sm text-white" />
            </div>
          </div>

          <div>
            <label className="text-xs text-secondary mb-1 block">Priority (Higher = Urgent)</label>
            <select value={priority} onChange={e => setPriority(e.target.value)} className="w-full bg-surface-elevated border border-white/10 rounded px-2 py-1 text-sm text-white">
              <option value="1">Normal (1)</option>
              <option value="5">High (5)</option>
              <option value="10">Urgent (10)</option>
            </select>
          </div>

          <button type="submit" className="w-full bg-blue-500 hover:bg-blue-600 text-white rounded py-2 text-sm font-bold transition-colors mt-2">
            Dispatch Task
          </button>
        </form>
      </div>
    </div>
  );
};
