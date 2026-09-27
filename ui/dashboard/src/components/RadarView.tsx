import type { RadarCluster } from '../types';

interface Props {
  clusters: RadarCluster[];
}

// SVG viewport size
const SIZE = 240;
const CX   = SIZE / 2;
const CY   = SIZE / 2;
// Max display range (meters) → maps to radius in SVG units
const MAX_RANGE_M = 60;
const R_MAX = SIZE / 2 - 12; // px radius for MAX_RANGE_M

function metersToRadius(range_m: number): number {
  return Math.min((range_m / MAX_RANGE_M) * R_MAX, R_MAX);
}

/** Convert polar (range, azimuth) to SVG (x, y).
 *  Azimuth 0 = straight ahead = top of the view.
 *  Positive azimuth = right. */
function polarToSvg(range_m: number, azimuth_deg: number): [number, number] {
  const r   = metersToRadius(range_m);
  const rad = (azimuth_deg * Math.PI) / 180;
  const sx  = CX + r * Math.sin(rad);
  const sy  = CY - r * Math.cos(rad); // y up = forward
  return [sx, sy];
}

function clusterColor(cluster: RadarCluster): string {
  const closing = cluster.doppler_mps > 0.5;
  if (!closing) return '#38bdf8'; // static / receding — cyan
  // closing: red for high closing speed
  const intensity = Math.min(cluster.doppler_mps / 8, 1);
  const r = Math.round(56 + 183 * intensity);
  const g = Math.round(189 - 140 * intensity);
  return `rgb(${r}, ${g}, 80)`;
}

const RING_RANGES = [15, 30, 45, 60];

export function RadarView({ clusters }: Props) {
  return (
    <section className="panel radar-panel">
      <div className="panel-title">◉ Radar Situational View</div>
      <div className="radar-svg-wrap">
        <svg
          className="radar-svg"
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          width={SIZE}
          height={SIZE}
          aria-label="Radar display"
        >
          {/* Range rings */}
          {RING_RANGES.map((r_m) => {
            const r_px = metersToRadius(r_m);
            return (
              <g key={r_m}>
                <circle
                  cx={CX} cy={CY} r={r_px}
                  fill="none" stroke="rgba(56,189,248,0.10)" strokeWidth={1}
                />
                <text
                  x={CX + 3}
                  y={CY - r_px + 10}
                  fontSize={8}
                  fill="rgba(56,189,248,0.35)"
                  fontFamily="monospace"
                >
                  {r_m}m
                </text>
              </g>
            );
          })}

          {/* Azimuth lines */}
          {[-30, -15, 0, 15, 30].map((deg) => {
            const rad  = (deg * Math.PI) / 180;
            const x2   = CX + R_MAX * Math.sin(rad);
            const y2   = CY - R_MAX * Math.cos(rad);
            return (
              <line
                key={deg}
                x1={CX} y1={CY} x2={x2} y2={y2}
                stroke="rgba(56,189,248,0.10)" strokeWidth={1}
                strokeDasharray={deg === 0 ? '4 3' : undefined}
              />
            );
          })}

          {/* Radar clusters */}
          {clusters.map((cl, i) => {
            const [sx, sy] = polarToSvg(cl.range_m, cl.azimuth_deg);
            const col      = clusterColor(cl);
            const closing  = cl.doppler_mps > 0.5;
            // Dot size scales with point_count and persistence
            const dotR     = 4 + cl.point_count * 1.2 + cl.persistence * 2;
            const glowR    = dotR + 5;
            
            // Determine if this is a critical object (very close + closing fast)
            const isCritical = cl.range_m < 30 && cl.doppler_mps > 5;
            const isWarning = cl.range_m < 60 && cl.doppler_mps > 3;
            
            return (
              <g key={i}>
                {/* Glow */}
                <circle 
                  cx={sx} cy={sy} r={glowR} fill={col} opacity={0.12}
                  className={isCritical ? 'radar-pulse-critical' : isWarning ? 'radar-pulse-warning' : ''}
                />
                {/* Core dot */}
                <circle cx={sx} cy={sy} r={dotR} fill={col} opacity={0.85} />
                {/* Velocity indicator (line in doppler direction) */}
                {closing && (
                  <line
                    x1={sx} y1={sy}
                    x2={sx}
                    y2={sy + Math.min(cl.doppler_mps * 3, 18)}
                    stroke={col} strokeWidth={1.5} opacity={0.7}
                    strokeLinecap="round"
                  />
                )}
                {/* Range label */}
                <text
                  x={sx + dotR + 3}
                  y={sy + 4}
                  fontSize={9}
                  fill="rgba(232,232,240,0.65)"
                  fontFamily="monospace"
                >
                  {cl.range_m.toFixed(0)}m
                </text>
                {/* CLOSING label for approaching objects */}
                {closing && cl.range_m < 80 && (
                  <text
                    x={sx - 20}
                    y={sy - dotR - 4}
                    fontSize={7}
                    fill={isCritical ? '#ef4444' : isWarning ? '#f97316' : '#38bdf8'}
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    CLOSING
                  </text>
                )}
              </g>
            );
          })}

          {/* Own vehicle marker */}
          <polygon
            points={`${CX},${CY - 9} ${CX - 6},${CY + 7} ${CX + 6},${CY + 7}`}
            fill="rgba(56,189,248,0.9)"
            stroke="#0f172a"
            strokeWidth={1.5}
          />

          {/* Outer boundary */}
          <circle cx={CX} cy={CY} r={R_MAX} fill="none" stroke="rgba(56,189,248,0.20)" strokeWidth={1} />
        </svg>
      </div>

      {clusters.length === 0 && (
        <p className="empty-state" style={{ textAlign: 'center', paddingBottom: 8 }}>
          No radar targets
        </p>
      )}

      {/* Legend */}
      <div style={{ padding: '4px 12px 8px', display: 'flex', gap: 16, fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
        <span style={{ color: '#38bdf8' }}>● Static</span>
        <span style={{ color: '#ef4444' }}>● Closing</span>
        <span>▲ Own vehicle</span>
      </div>
    </section>
  );
}
