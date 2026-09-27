/**
 * RadarPerceptionPanel — Square radar perception visualization.
 *
 * Displays radar clusters in a square 1:1 aspect ratio with:
 * - Polar radar field-of-view visualization
 * - Range rings and azimuth guides
 * - Detected clusters as distinct targets
 * - Range and doppler visualization
 * - Clear "SIMULATED" badge
 *
 * All data from the actual simulator — no fabricated objects.
 */

import type { RadarCluster } from '../types';

const RADAR_SIZE   = 320;
const CX = RADAR_SIZE / 2, CY = RADAR_SIZE / 2;
const MAX_RANGE_M  = 60;
const R_MAX        = RADAR_SIZE / 2 - 20;
const RING_RANGES  = [15, 30, 45, 60];

function toRadius(range_m: number) { return Math.min((range_m / MAX_RANGE_M) * R_MAX, R_MAX); }
function polarToSvg(range_m: number, az: number): [number, number] {
  const r   = toRadius(range_m);
  const rad = (az * Math.PI) / 180;
  return [CX + r * Math.sin(rad), CY - r * Math.cos(rad)];
}
function clusterColor(dop: number) {
  if (dop <= 0.5) return '#38bdf8';
  const t = Math.min(dop / 8, 1);
  return `rgb(${Math.round(56+183*t)},${Math.round(189-140*t)},80)`;
}

interface Props {
  clusters: RadarCluster[];
  quality: number;
  frameNumber: number | null;
}

export function RadarPerceptionPanel({ clusters, quality, frameNumber }: Props) {
  const qualityColor = quality >= 0.7 ? '#22c55e' : quality >= 0.4 ? '#f59e0b' : '#ef4444';
  const qualityStatus = quality >= 0.7 ? 'ACTIVE' : quality >= 0.4 ? 'DEGRADED' : 'POOR';

  return (
    <div className="perception-panel">
      <div className="perception-header">
        <div className="perception-title">
          <span className="perception-icon">◎</span>
          <span>RADAR PERCEPTION</span>
        </div>
        <div className="perception-meta">
          <span className="perception-status" style={{color: qualityColor}}>{qualityStatus}</span>
          <span className="perception-sep">|</span>
          <span className="perception-frame">F{frameNumber ?? '—'}</span>
        </div>
      </div>

      <div className="perception-body">
        <div className="radar-scene-wrapper">
          <svg
            className="radar-scene-svg"
            viewBox={`0 0 ${RADAR_SIZE} ${RADAR_SIZE}`}
            width={RADAR_SIZE}
            height={RADAR_SIZE}
            aria-label="Radar situational view"
          >
            {/* Background grid */}
            <defs>
              <pattern id="radar-grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(56,189,248,0.04)" strokeWidth="0.5"/>
              </pattern>
            </defs>
            <rect width={RADAR_SIZE} height={RADAR_SIZE} fill="url(#radar-grid)"/>

            {/* Range rings */}
            {RING_RANGES.map(r_m => {
              const r_px = toRadius(r_m);
              return (
                <g key={r_m}>
                  <circle cx={CX} cy={CY} r={r_px} fill="none" stroke="rgba(56,189,248,0.15)" strokeWidth={1}/>
                  <text x={CX+4} y={CY-r_px+11} fontSize={9} fill="rgba(56,189,248,0.4)" fontFamily="monospace" fontWeight="700">
                    {r_m}m
                  </text>
                </g>
              );
            })}

            {/* Azimuth lines */}
            {[-30,-15,0,15,30].map(deg => {
              const rad=(deg*Math.PI)/180;
              return (
                <line key={deg}
                  x1={CX} y1={CY}
                  x2={CX+R_MAX*Math.sin(rad)} y2={CY-R_MAX*Math.cos(rad)}
                  stroke="rgba(56,189,248,0.12)" strokeWidth={deg===0?1.5:1}
                  strokeDasharray={deg===0?'4 3':undefined}
                />
              );
            })}

            {/* Compass labels */}
            <text x={CX-4} y={16}  fontSize={10} fill="rgba(56,189,248,0.5)" fontFamily="monospace" fontWeight="700">N</text>
            <text x={CX-4} y={RADAR_SIZE-8} fontSize={10} fill="rgba(56,189,248,0.3)" fontFamily="monospace">S</text>
            <text x={10}   y={CY+4} fontSize={10} fill="rgba(56,189,248,0.3)" fontFamily="monospace">W</text>
            <text x={RADAR_SIZE-18} y={CY+4} fontSize={10} fill="rgba(56,189,248,0.3)" fontFamily="monospace">E</text>

            {/* Radar clusters */}
            {clusters.map((cl, i) => {
              const [sx, sy] = polarToSvg(cl.range_m, cl.azimuth_deg);
              const col = clusterColor(cl.doppler_mps);
              const dotR = 5 + cl.point_count * 1.0 + cl.persistence * 2;
              const isClosing = cl.doppler_mps > 0.5;
              
              return (
                <g key={i}>
                  {/* Outer glow */}
                  <circle cx={sx} cy={sy} r={dotR+6} fill={col} opacity={0.15}/>
                  {/* Main dot */}
                  <circle cx={sx} cy={sy} r={dotR} fill={col} opacity={0.9}/>
                  {/* Doppler arrow for closing targets */}
                  {isClosing && (
                    <g>
                      <line x1={sx} y1={sy} x2={sx} y2={sy+Math.min(cl.doppler_mps*3,20)}
                        stroke={col} strokeWidth={2} opacity={0.8} strokeLinecap="round"/>
                      <polygon 
                        points={`${sx},${sy+Math.min(cl.doppler_mps*3,20)+4} ${sx-3},${sy+Math.min(cl.doppler_mps*3,20)-2} ${sx+3},${sy+Math.min(cl.doppler_mps*3,20)-2}`}
                        fill={col} opacity={0.8}
                      />
                    </g>
                  )}
                  {/* Range label */}
                  <text x={sx+dotR+4} y={sy-4} fontSize={9} fill="rgba(232,232,240,0.7)" fontFamily="monospace" fontWeight="600">
                    {cl.range_m.toFixed(1)}m
                  </text>
                  {/* Doppler label for closing */}
                  {isClosing && (
                    <text x={sx+dotR+4} y={sy+8} fontSize={8} fill={col} fontFamily="monospace">
                      +{cl.doppler_mps.toFixed(1)}m/s
                    </text>
                  )}
                  {/* Target ID */}
                  <text x={sx} y={sy+3} fontSize={9} fill="#000" fontFamily="monospace" fontWeight="700" textAnchor="middle">
                    {i+1}
                  </text>
                </g>
              );
            })}

            {/* Own vehicle */}
            <g>
              <polygon
                points={`${CX},${CY-12} ${CX-8},${CY+10} ${CX+8},${CY+10}`}
                fill="rgba(56,189,248,0.95)"
                stroke="#000" strokeWidth={1.5}
              />
              <text x={CX} y={CY+26} fontSize={9} textAnchor="middle"
                fill="rgba(56,189,248,0.6)" fontFamily="monospace" fontWeight="600">EGO</text>
            </g>

            {/* Outer ring */}
            <circle cx={CX} cy={CY} r={R_MAX} fill="none" stroke="rgba(56,189,248,0.25)" strokeWidth={1.5}/>

            {/* Field of view arc */}
            <path
              d={`M ${CX + R_MAX * Math.sin(-30 * Math.PI / 180)} ${CY - R_MAX * Math.cos(-30 * Math.PI / 180)} 
                  A ${R_MAX} ${R_MAX} 0 0 1 ${CX + R_MAX * Math.sin(30 * Math.PI / 180)} ${CY - R_MAX * Math.cos(30 * Math.PI / 180)}`}
              fill="none"
              stroke="rgba(56,189,248,0.4)"
              strokeWidth={2}
            />
          </svg>

          <div className="radar-scene-badge">SIMULATED</div>
          <div className="radar-scene-info">
            <div className="radar-info-row">
              <span className="radar-info-label">TARGETS</span>
              <span className="radar-info-value">{clusters.length}</span>
            </div>
            <div className="radar-info-row">
              <span className="radar-info-label">QUALITY</span>
              <span className="radar-info-value" style={{color: qualityColor}}>
                {(quality * 100).toFixed(0)}%
              </span>
            </div>
            <div className="radar-info-row">
              <span className="radar-info-label">RANGE</span>
              <span className="radar-info-value">{MAX_RANGE_M}m</span>
            </div>
          </div>
        </div>
      </div>

      <div className="perception-footer">
        <div className="perception-legend-item">
          <span style={{color:'#38bdf8',fontSize:10}}>●</span>
          <span>Static</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'#ef4444',fontSize:10}}>●</span>
          <span>Closing</span>
        </div>
        <div className="perception-legend-item">
          <span style={{fontSize:10}}>↓</span>
          <span>Doppler</span>
        </div>
        <div className="perception-legend-item" style={{marginLeft:'auto'}}>
          <span>60° FOV</span>
        </div>
      </div>
    </div>
  );
}
