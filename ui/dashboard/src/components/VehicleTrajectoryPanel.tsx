/**
 * VehicleTrajectoryPanel — Top-down vehicle trajectory prediction visualization.
 *
 * Displays:
 * - Ego vehicle position and heading
 * - Tracked objects with their positions
 * - Predicted trajectories based on velocity vectors
 * - Collision risk zones
 * - Path overlap visualization
 *
 * All predictions are based on actual track velocity data from the backend.
 * No fabricated trajectory horizons or uncertainty values.
 */

import { useMemo } from 'react';
import type { Track, RiskAssessment } from '../types';

const CANVAS_SIZE = 400;
const SCALE = 4; // pixels per meter
const CX = CANVAS_SIZE / 2;
const CY = CANVAS_SIZE / 2;

const CLS_ICON: Record<string, string> = {
  person: '🚶',
  vehicle: '🚛',
  large_obstacle: '⬛',
  unknown: '◆',
};

const CLS_LABEL: Record<string, string> = {
  person: 'Person',
  vehicle: 'Vehicle',
  large_obstacle: 'Obstacle',
  unknown: 'Unknown',
};

interface Props {
  tracks: Track[];
  risks: RiskAssessment[];
  frameNumber: number | null;
}

export function VehicleTrajectoryPanel({ tracks, risks, frameNumber }: Props) {
  // Risk map for quick lookup
  const riskMap = useMemo(() => {
    const map = new Map<number, RiskAssessment>();
    risks.forEach(r => map.set(r.track_id, r));
    return map;
  }, [risks]);

  // Find highest risk track
  const highestRiskTrack = useMemo((): Track | null => {
    const RISK_ORDER = { safe: 0, caution: 1, warning: 2, critical: 3 };
    let maxRisk = -1;
    let maxTrack: Track | null = null;
    tracks.forEach(t => {
      const risk = riskMap.get(t.track_id);
      if (risk) {
        const order = RISK_ORDER[risk.risk_state];
        if (order > maxRisk) {
          maxRisk = order;
          maxTrack = t;
        }
      }
    });
    return maxTrack;
  }, [tracks, riskMap]);

  // Convert world coordinates to canvas
  const worldToCanvas = (x: number, y: number): [number, number] => {
    // Vehicle frame: +X right, +Y forward
    return [CX + x * SCALE, CY - y * SCALE];
  };

  // Predict future position based on velocity (simple linear extrapolation)
  const predictPosition = (track: Track, seconds: number): [number, number] => {
    const [x, y] = track.position_xy;
    const [vx, vy] = track.velocity_xy;
    return [x + vx * seconds, y + vy * seconds];
  };

  return (
    <div className="perception-panel">
      <div className="perception-header">
        <div className="perception-title">
          <span className="perception-icon">⊙</span>
          <span>VEHICLE TRAJECTORY</span>
        </div>
        <div className="perception-meta">
          <span className="perception-frame">F{frameNumber ?? '—'}</span>
          <span className="perception-sep">|</span>
          <span className="trajectory-tracks">{tracks.length} TRACKS</span>
        </div>
      </div>

      <div className="perception-body">
        <svg
          className="trajectory-scene-svg"
          viewBox={`0 0 ${CANVAS_SIZE} ${CANVAS_SIZE}`}
          width="100%"
          height="100%"
          aria-label="Vehicle trajectory prediction"
        >
          {/* Background grid */}
          <defs>
            <pattern id="traj-grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(56,189,248,0.06)" strokeWidth="0.5"/>
            </pattern>
            <pattern id="traj-grid-major" width="200" height="200" patternUnits="userSpaceOnUse">
              <path d="M 200 0 L 0 0 0 200" fill="none" stroke="rgba(56,189,248,0.12)" strokeWidth="1"/>
            </pattern>
          </defs>
          <rect width={CANVAS_SIZE} height={CANVAS_SIZE} fill="rgba(6,12,24,0.8)"/>
          <rect width={CANVAS_SIZE} height={CANVAS_SIZE} fill="url(#traj-grid)"/>
          <rect width={CANVAS_SIZE} height={CANVAS_SIZE} fill="url(#traj-grid-major)"/>

          {/* Range circles */}
          {[10, 20, 30, 40].map(r => (
            <circle
              key={r}
              cx={CX}
              cy={CY}
              r={r * SCALE}
              fill="none"
              stroke="rgba(56,189,248,0.10)"
              strokeWidth={0.5}
            />
          ))}

          {/* Center axes */}
          <line x1={0} y1={CY} x2={CANVAS_SIZE} y2={CY} stroke="rgba(56,189,248,0.08)" strokeWidth={1}/>
          <line x1={CX} y1={0} x2={CX} y2={CANVAS_SIZE} stroke="rgba(56,189,248,0.08)" strokeWidth={1}/>

          {/* Range labels */}
          <text x={CX+5} y={CY-10*SCALE+12} fontSize={9} fill="rgba(56,189,248,0.35)" fontFamily="monospace">10m</text>
          <text x={CX+5} y={CY-20*SCALE+12} fontSize={9} fill="rgba(56,189,248,0.35)" fontFamily="monospace">20m</text>
          <text x={CX+5} y={CY-30*SCALE+12} fontSize={9} fill="rgba(56,189,248,0.35)" fontFamily="monospace">30m</text>

          {/* Draw tracks */}
          {tracks.map(track => {
            const [cx_canvas, cy_canvas] = worldToCanvas(track.position_xy[0], track.position_xy[1]);
            const risk = riskMap.get(track.track_id);
            const isHighRisk = risk && (risk.risk_state === 'warning' || risk.risk_state === 'critical');
            const isHighest = highestRiskTrack?.track_id === track.track_id;
            
            // Color based on risk
            let color = '#38bdf8';
            if (risk) {
              if (risk.risk_state === 'critical') color = '#ef4444';
              else if (risk.risk_state === 'warning') color = '#f97316';
              else if (risk.risk_state === 'caution') color = '#f59e0b';
            }

            // Velocity vector (speed)
            const speed = Math.hypot(track.velocity_xy[0], track.velocity_xy[1]);
            const isMoving = speed > 0.3;

            // Predicted trajectory (3 second horizon)
            const predictions: Array<[number, number]> = [];
            if (isMoving) {
              for (let t = 0.5; t <= 3; t += 0.5) {
                predictions.push(predictPosition(track, t));
              }
            }

            return (
              <g key={track.track_id}>
                {/* Historical path */}
                {track.history.length > 1 && (
                  <path
                    d={track.history.map((pos, i) => {
                      const [px, py] = worldToCanvas(pos[0], pos[1]);
                      return `${i === 0 ? 'M' : 'L'} ${px} ${py}`;
                    }).join(' ')}
                    fill="none"
                    stroke={color}
                    strokeWidth={1.5}
                    strokeOpacity={0.3}
                    strokeDasharray="2 2"
                  />
                )}

                {/* Predicted trajectory */}
                {predictions.length > 0 && (
                  <g>
                    <path
                      d={`M ${cx_canvas} ${cy_canvas} ${predictions.map(p => {
                        const [px, py] = worldToCanvas(p[0], p[1]);
                        return `L ${px} ${py}`;
                      }).join(' ')}`}
                      fill="none"
                      stroke={color}
                      strokeWidth={2}
                      strokeOpacity={0.6}
                      strokeDasharray="4 2"
                    />
                    {/* Future position markers */}
                    {predictions.map((p, i) => {
                      const [px, py] = worldToCanvas(p[0], p[1]);
                      return (
                        <circle
                          key={i}
                          cx={px}
                          cy={py}
                          r={2}
                          fill={color}
                          opacity={0.4 - i * 0.05}
                        />
                      );
                    })}
                  </g>
                )}

                {/* Risk zone for high-risk tracks */}
                {isHighRisk && (
                  <circle
                    cx={cx_canvas}
                    cy={cy_canvas}
                    r={20}
                    fill={color}
                    opacity={0.1}
                    stroke={color}
                    strokeWidth={1}
                    strokeDasharray="3 3"
                  />
                )}

                {/* Track marker */}
                <circle
                  cx={cx_canvas}
                  cy={cy_canvas}
                  r={isHighest ? 10 : 8}
                  fill={color}
                  opacity={0.9}
                  stroke={isHighest ? '#fff' : color}
                  strokeWidth={isHighest ? 2 : 1}
                />

                {/* Track ID */}
                <text
                  x={cx_canvas}
                  y={cy_canvas + 3}
                  fontSize={10}
                  fontFamily="monospace"
                  fontWeight="700"
                  fill="#000"
                  textAnchor="middle"
                >
                  {track.track_id}
                </text>

                {/* Track info */}
                <text
                  x={cx_canvas}
                  y={cy_canvas - 14}
                  fontSize={9}
                  fontFamily="monospace"
                  fill={color}
                  textAnchor="middle"
                >
                  {CLS_LABEL[track.cls] ?? track.cls}
                </text>

                {/* Distance label */}
                {risk && (
                  <text
                    x={cx_canvas}
                    y={cy_canvas + 24}
                    fontSize={8}
                    fontFamily="monospace"
                    fill="rgba(232,232,240,0.6)"
                    textAnchor="middle"
                  >
                    {risk.distance_m.toFixed(1)}m
                  </text>
                )}
              </g>
            );
          })}

          {/* Ego vehicle */}
          <g>
            {/* Vehicle body */}
            <rect
              x={CX - 8}
              y={CY - 12}
              width={16}
              height={24}
              rx={2}
              fill="rgba(56,189,248,0.9)"
              stroke="#000"
              strokeWidth={1.5}
            />
            {/* Front indicator */}
            <rect
              x={CX - 6}
              y={CY - 16}
              width={12}
              height={4}
              rx={1}
              fill="rgba(56,189,248,0.7)"
            />
            {/* Direction arrow */}
            <path
              d={`M ${CX} ${CY-20} L ${CX-4} ${CY-14} L ${CX+4} ${CY-14} Z`}
              fill="rgba(56,189,248,0.9)"
            />
            <text
              x={CX}
              y={CY + 30}
              fontSize={10}
              fontFamily="monospace"
              fontWeight="700"
              fill="rgba(56,189,248,0.7)"
              textAnchor="middle"
            >
              EGO VEHICLE
            </text>
          </g>
        </svg>

        {/* Info overlay - made more compact for square format */}
        {highestRiskTrack && (
          <div className="trajectory-selected-track-compact">
            <div className="trajectory-selected-header">HIGHEST RISK</div>
            <div className="trajectory-selected-body-compact">
              <div className="trajectory-selected-row-compact">
                <span className="trajectory-selected-value">#{highestRiskTrack.track_id}</span>
              </div>
              <div className="trajectory-selected-row-compact">
                <span className="trajectory-selected-value">
                  {CLS_ICON[highestRiskTrack.cls]} {CLS_LABEL[highestRiskTrack.cls] ?? highestRiskTrack.cls}
                </span>
              </div>
              {riskMap.get(highestRiskTrack.track_id) && (
                <>
                  <div className="trajectory-selected-row-compact">
                    <span className="trajectory-selected-value">
                      {riskMap.get(highestRiskTrack.track_id)!.distance_m.toFixed(1)} m
                    </span>
                  </div>
                  {riskMap.get(highestRiskTrack.track_id)!.ttc_s !== null && (
                    <div className="trajectory-selected-row-compact">
                      <span className="trajectory-selected-value">
                        TTC: {riskMap.get(highestRiskTrack.track_id)!.ttc_s!.toFixed(1)} s
                      </span>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="perception-footer">
        <div className="perception-legend-item">
          <span style={{color:'#38bdf8',fontSize:10}}>●</span>
          <span>Safe</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'#f59e0b',fontSize:10}}>●</span>
          <span>Caution</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'#f97316',fontSize:10}}>●</span>
          <span>Warning</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'#ef4444',fontSize:10}}>●</span>
          <span>Critical</span>
        </div>
        <div className="perception-legend-item" style={{marginLeft:'auto'}}>
          <span>3s Horizon</span>
        </div>
      </div>
    </div>
  );
}
