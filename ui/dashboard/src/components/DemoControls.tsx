/**
 * DemoControls — simulation mode scenario switcher.
 *
 * Displays one button per scenario.  Clicking sends POST /api/scenario to the
 * backend.  The active scenario is highlighted.  A "SIMULATION MODE" label
 * makes it unmistakably clear that the data is synthetic.
 */

import { useCallback, useEffect, useState } from 'react';
import { HTTP_BASE } from '../config';
import type { ScenarioInfo } from '../types';

interface Props {
  /** Current scenario from the live WS frame (or null before first frame) */
  currentScenario: string | null;
}

const SCENARIO_LABELS: Record<string, string> = {
  SAFE:                'SAFE',
  CAUTION:             'CAUTION',
  WARNING:             'WARNING',
  CRITICAL:            'CRITICAL',
  PEDESTRIAN_APPROACH: 'PEDESTRIAN',
  MULTI_TARGET:        'MULTI TARGET',
  COLLISION_DEMO:      'COLLISION DEMO',
};

const SCENARIO_COLORS: Record<string, string> = {
  SAFE:                'var(--safe)',
  CAUTION:             'var(--caution)',
  WARNING:             'var(--warning)',
  CRITICAL:            'var(--critical)',
  PEDESTRIAN_APPROACH: '#a78bfa',
  MULTI_TARGET:        'var(--accent)',
  COLLISION_DEMO:      '#f43f5e',
};

export function DemoControls({ currentScenario }: Props) {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch available scenarios once on mount
  useEffect(() => {
    fetch(`${HTTP_BASE}/api/scenarios`)
      .then(r => r.json())
      .then(data => setScenarios(data.scenarios ?? []))
      .catch(() => setError('Could not load scenarios'));
  }, []);

  const selectScenario = useCallback(async (name: string) => {
    setPending(name);
    setError(null);
    try {
      const resp = await fetch(`${HTTP_BASE}/api/scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: name }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        setError(body.detail ?? `HTTP ${resp.status}`);
      }
    } catch {
      setError('Network error');
    } finally {
      setPending(null);
    }
  }, []);

  const active = currentScenario ?? 'SAFE';

  return (
    <div className="demo-controls">
      <div className="demo-header">
        <span className="demo-sim-badge">⚙ SIMULATION MODE</span>
        <span className="demo-active-label">
          SCENARIO:&nbsp;<span className="demo-active-name">{active}</span>
        </span>
      </div>

      <div className="demo-buttons">
        {scenarios.map(s => {
          const isActive  = s.name === active;
          const isPending = s.name === pending;
          const color     = SCENARIO_COLORS[s.name] ?? 'var(--accent)';
          return (
            <button
              key={s.name}
              data-testid={`scenario-btn-${s.name}`}
              className={`demo-btn${isActive ? ' demo-btn-active' : ''}`}
              style={isActive ? { borderColor: color, color, boxShadow: `0 0 8px ${color}44` } : {}}
              title={s.description}
              disabled={pending !== null}
              onClick={() => selectScenario(s.name)}
            >
              {isPending ? '…' : (SCENARIO_LABELS[s.name] ?? s.name)}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="demo-error">{error}</div>
      )}
    </div>
  );
}