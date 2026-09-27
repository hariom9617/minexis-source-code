/**
 * FusionBar — Compact adaptive sensor fusion strip.
 *
 * Shows: Radar quality → Thermal quality → Fusion Engine → Fused objects → Confidence ring.
 * All values come from real backend data — nothing hardcoded.
 */

import type { FusedObject } from '../types';

interface Props {
  radarQuality:   number;   // 0-1
  thermalQuality: number;   // 0-1
  fusedObjects:   FusedObject[];
}

const CLS_LABEL: Record<string, string> = {
  person:         'Person',
  vehicle:        'Vehicle',
  large_obstacle: 'Obstacle',
  unknown:        'Object',
};

/** Average fused confidence — used for the ring */
function avgConf(objects: FusedObject[]): number {
  if (!objects.length) return 0;
  return objects.reduce((s, o) => s + o.confidence, 0) / objects.length;
}

/** SVG circle ring for confidence */
function ConfRing({ value }: { value: number }) {
  const R    = 26;
  const circ = 2 * Math.PI * R;
  const dash = circ * value;
  const pct  = Math.round(value * 100);
  return (
    <div className="fb-confidence">
      <div className="fb-conf-ring">
        <svg width={64} height={64} viewBox="0 0 64 64">
          {/* Track */}
          <circle cx={32} cy={32} r={R} fill="none"
            stroke="rgba(56,189,248,0.12)" strokeWidth={5}/>
          {/* Fill */}
          <circle cx={32} cy={32} r={R} fill="none"
            stroke={value>0.7?'#22c55e':value>0.4?'#f59e0b':'#ef4444'}
            strokeWidth={5}
            strokeDasharray={`${dash} ${circ-dash}`}
            strokeDashoffset={0}
            strokeLinecap="round"
            style={{transform:'rotate(-90deg)',transformOrigin:'center',transition:'stroke-dasharray .5s'}}
          />
        </svg>
        <div className="fb-conf-val">{pct}%</div>
      </div>
      <div className="fb-conf-label">FUSION CONF.</div>
    </div>
  );
}

export function FusionBar({ radarQuality, thermalQuality, fusedObjects }: Props) {
  const conf = avgConf(fusedObjects);

  return (
    <div className="fusion-bar">
      <div className="fusion-bar-title">⊕ Adaptive Sensor Fusion</div>
      <div className="fusion-bar-body">

        {/* Source quality bars */}
        <div className="fb-sources">
          <div className="fb-source-row">
            <span className="fb-src-label">◎ Radar</span>
            <div className="fb-bar">
              <div className="fb-fill radar" style={{width:`${(radarQuality*100).toFixed(0)}%`}}/>
            </div>
            <span className="fb-pct">{(radarQuality*100).toFixed(0)}%</span>
          </div>
          <div className="fb-source-row">
            <span className="fb-src-label">⬤ Thermal</span>
            <div className="fb-bar">
              <div className="fb-fill thermal" style={{width:`${(thermalQuality*100).toFixed(0)}%`}}/>
            </div>
            <span className="fb-pct">{(thermalQuality*100).toFixed(0)}%</span>
          </div>
        </div>

        <div className="fb-arrow">→</div>

        {/* Fusion engine */}
        <div className="fb-engine">
          <div className="fb-engine-title">FUSION ENGINE</div>
          <div className="fb-engine-sub">Adaptive Weighting &amp;<br/>Confidence Scoring</div>
        </div>

        <div className="fb-arrow">→</div>

        {/* Fused objects */}
        <div className="fb-objects">
          {fusedObjects.length === 0 ? (
            <div style={{fontSize:10,color:'var(--text-dim)',fontStyle:'italic'}}>No fused objects</div>
          ) : fusedObjects.slice(0,3).map((f, i) => (
            <div className="fb-obj-row" key={i}>
              <span className="fb-obj-name">{CLS_LABEL[f.cls]??f.cls}</span>
              <div className="fb-obj-bar">
                <div className="fb-obj-fill" style={{width:`${(f.confidence*100).toFixed(0)}%`}}/>
              </div>
              <span className="fb-obj-conf">{f.confidence.toFixed(2)}</span>
            </div>
          ))}
        </div>

        <div className="fb-arrow">→</div>

        {/* Confidence ring */}
        <ConfRing value={conf} />
      </div>
    </div>
  );
}
