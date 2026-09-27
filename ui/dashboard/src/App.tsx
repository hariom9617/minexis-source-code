/**
 * MINEXIS Dashboard — Complete Refactored Perception UI.
 *
 * Structure:
 *   Header  (logo + status + simulation controls)
 *   ─────────────────────────────────────────────────────────────────────────
 *   [ Thermal Perception Panel ] [ Radar Perception Panel ]     (Square 1:1)
 *   ─────────────────────────────────────────────────────────────────────────
 *   [ Vehicle Trajectory Prediction Panel ]                     (Wide)
 *   ─────────────────────────────────────────────────────────────────────────
 *   [ Sensor Quality ] [ Risk Summary ]  [ Active Alerts ]  [ Active Tracks ]
 *   ─────────────────────────────────────────────────────────────────────────
 *   Footer  (performance metrics)
 *
 * All data from actual backend — no fabricated values.
 * Industrial-grade ADAS monitoring interface for Smart India Hackathon.
 */

import './styles/dashboard.css';

import { useCallback, useEffect, useState } from 'react';
import { useLivePipeline }          from './hooks/useLivePipeline';
import { useWarningSound }          from './hooks/useWarningSound';
import { ThermalPerceptionPanel }   from './components/ThermalPerceptionPanel';
import { RadarPerceptionPanel }     from './components/RadarPerceptionPanel';
import { VehicleTrajectoryPanel }   from './components/VehicleTrajectoryPanel';
import { HTTP_BASE }                from './config';
import type {
  ConnectionState, LiveFrame, RiskAssessment,
  ScenarioInfo, SensorModeResponse, Track,
} from './types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const RISK_ORDER: Record<string, number> = { safe:0, caution:1, warning:2, critical:3 };

function worstRisk(risks: RiskAssessment[]): RiskAssessment | null {
  if (!risks.length) return null;
  return risks.reduce((a,b) => RISK_ORDER[b.risk_state]>RISK_ORDER[a.risk_state] ? b : a);
}

const RISK_ICON:  Record<string,string> = { safe:'✓', caution:'◆', warning:'▲', critical:'⬟' };
const RISK_LABEL: Record<string,string> = { safe:'ALL CLEAR', caution:'CAUTION', warning:'WARNING', critical:'CRITICAL' };
const RISK_SUB:   Record<string,string> = {
  safe:     'No active threats detected',
  caution:  'Object in caution zone',
  warning:  'Object closing on path',
  critical: 'Imminent collision risk!',
};

const CLS_ICON: Record<string,string>  = { person:'🚶', vehicle:'🚛', large_obstacle:'⬛', unknown:'◆' };
const CLS_LABEL: Record<string,string> = { person:'Person', vehicle:'Vehicle', large_obstacle:'Obstacle', unknown:'Unknown' };

// ---------------------------------------------------------------------------
// SIMULATION MODE BADGE Component
// ---------------------------------------------------------------------------
function SimulationBadge() {
  return (
    <div className="simulation-mode-badge">
      <div className="simulation-mode-icon">⚙</div>
      <div className="simulation-mode-text">
        <div className="simulation-mode-title">SIMULATION MODE</div>
        <div className="simulation-mode-subtitle">NOT LIVE HARDWARE</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components (inline for locality)
// ---------------------------------------------------------------------------

// Header
function Header({
  frame, connState, sensorMode, lastUpdate, onReconnect,
  currentScenario, scenarios, onSelectScenario,
  soundEnabled, onToggleSound,
}: {
  frame: LiveFrame|null;
  connState: ConnectionState;
  sensorMode: SensorModeResponse|null;
  lastUpdate: number|null;
  onReconnect: ()=>void;
  currentScenario: string;
  scenarios: ScenarioInfo[];
  onSelectScenario: (n:string)=>void;
  soundEnabled: boolean;
  onToggleSound: ()=>void;
}) {
  const isLive   = connState==='connected' && frame!==null;
  const needsRec = connState==='disconnected'||connState==='error';
  const isReal   = sensorMode?.label==='REAL';

  const CONN_LABELS: Record<ConnectionState,string> = {
    connected:'CONNECTED', connecting:'CONNECTING', reconnecting:'RECONNECTING',
    disconnected:'DISCONNECTED', error:'ERROR',
  };

  const SCENARIO_COLORS: Record<string,string> = {
    SAFE:'var(--safe)', CAUTION:'var(--caution)', WARNING:'var(--warning)',
    CRITICAL:'var(--critical)', PEDESTRIAN_APPROACH:'#a78bfa', MULTI_TARGET:'var(--accent)',
    COLLISION_DEMO:'#f43f5e',
  };
  const SCENARIO_LABELS: Record<string,string> = {
    SAFE:'SAFE', CAUTION:'CAUTION', WARNING:'WARNING', CRITICAL:'CRITICAL',
    PEDESTRIAN_APPROACH:'PEDESTRIAN', MULTI_TARGET:'MULTI TARGET',
    COLLISION_DEMO:'COLLISION DEMO',
  };

  return (
    <header className="dash-header">
      {/* Brand */}
      <div className="hdr-brand">
        <div className="hdr-logo">MINEXIS</div>
        <div className="hdr-tagline">Intelligent Mine Vehicle Safety System</div>
      </div>

      <div className="hdr-div"/>

      {isLive && (
        <div className="hdr-live">
          <div className="pulse-dot"/>
          LIVE
        </div>
      )}

      <div className={`hdr-conn ${connState}`}>{CONN_LABELS[connState]}</div>

      {sensorMode && (
        <div className={`hdr-sensor-mode${isReal?' real':''}`}>
          SENSOR: {sensorMode.label}
        </div>
      )}

      {needsRec && (
        <button className="hdr-reconnect" onClick={onReconnect}>RECONNECT</button>
      )}

      <div className="hdr-div"/>

      {/* Sound toggle button */}
      <button 
        className={`hdr-sound-btn${soundEnabled?' active':''}`}
        onClick={onToggleSound}
        title={soundEnabled ? 'Sound enabled (click to mute)' : 'Sound disabled (click to enable)'}
      >
        {soundEnabled ? '🔊 SOUND ON' : '🔇 SOUND OFF'}
      </button>

      <div className="hdr-div"/>

      {/* Simulation controls */}
      <div className="sim-controls">
        <span className="sim-badge">⚙ SIMULATION MODE</span>
        <span className="sim-scenario-label">
          SCENARIO:&nbsp;<span className="sim-scenario-name">{currentScenario}</span>
        </span>
        <div className="sim-btns">
          {scenarios.map(s => {
            const isActive = s.name===currentScenario;
            const color    = SCENARIO_COLORS[s.name]??'var(--accent)';
            return (
              <button
                key={s.name}
                data-testid={`scenario-btn-${s.name}`}
                className={`sim-btn${isActive?' active':''}`}
                style={isActive?{borderColor:color,color,boxShadow:`0 0 6px ${color}44`}:{}}
                title={s.description}
                onClick={() => onSelectScenario(s.name)}
              >
                {SCENARIO_LABELS[s.name]??s.name}
              </button>
            );
          })}
        </div>
      </div>

      {/* Right meta */}
      <div className="hdr-right">
        <div className="hdr-frame">
          FRAME <b>{frame?.frame_number??'—'}</b>
          {lastUpdate && <> &nbsp;{new Date(lastUpdate).toLocaleTimeString()}</>}
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Bottom Cards Row
// ---------------------------------------------------------------------------
function BottomCards({ frame }: { frame: LiveFrame|null }) {
  const level   = frame?.highest_risk ?? 'safe';
  const threat  = frame ? worstRisk(frame.risks) : null;
  const alerts  = frame?.alerts ?? [];
  const tracks  = frame?.tracks ?? [];

  const sortedAlerts = [...alerts].sort((a,b)=>RISK_ORDER[b.risk_state]-RISK_ORDER[a.risk_state]);

  const qualityColor = (q: number) => {
    if (q >= 0.7) return '#22c55e';
    if (q >= 0.4) return '#f59e0b';
    return '#ef4444';
  };

  const thermalQ = frame?.thermal_quality ?? 0;
  const radarQ = frame?.radar_quality ?? 0;

  return (
    <div className="bottom-cards">
      {/* Sensor Quality */}
      <div className="sensor-quality-card">
        <div className="sq-title">◈ Sensor Quality</div>
        <div className="sq-sensors">
          <div className="sq-sensor">
            <div className="sq-sensor-header">
              <span className="sq-sensor-icon thermal">⬤</span>
              <span className="sq-sensor-name">THERMAL</span>
            </div>
            <div className="sq-bar">
              <div className="sq-fill" style={{width: `${(thermalQ*100).toFixed(0)}%`, background: qualityColor(thermalQ)}}/>
            </div>
            <span className="sq-pct" style={{color: qualityColor(thermalQ)}}>{(thermalQ*100).toFixed(0)}%</span>
          </div>
          <div className="sq-sensor">
            <div className="sq-sensor-header">
              <span className="sq-sensor-icon radar">◎</span>
              <span className="sq-sensor-name">RADAR</span>
            </div>
            <div className="sq-bar">
              <div className="sq-fill" style={{width: `${(radarQ*100).toFixed(0)}%`, background: qualityColor(radarQ)}}/>
            </div>
            <span className="sq-pct" style={{color: qualityColor(radarQ)}}>{(radarQ*100).toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Risk */}
      <div className="risk-card">
        <div className="risk-card-title">◈ Risk Status</div>
        <div className={`risk-badge-new ${level}`}>
          <div className="risk-icon">{RISK_ICON[level]}</div>
          <div className="risk-text-block">
            <div className="risk-state-text">{RISK_LABEL[level]}</div>
            <div className="risk-sub">{RISK_SUB[level]}</div>
          </div>
        </div>
        {threat && (
          <div className="risk-details-grid">
            <div className="risk-detail-row">
              <span className="lbl">Track</span>
              <span className="val accent">#{threat.track_id}</span>
            </div>
            <div className="risk-detail-row">
              <span className="lbl">Distance</span>
              <span className="val">{threat.distance_m.toFixed(1)} m</span>
            </div>
            <div className="risk-detail-row">
              <span className="lbl">TTC</span>
              <span className="val">{threat.ttc_s!=null?threat.ttc_s.toFixed(1)+' s':'N/A'}</span>
            </div>
            {frame?.alerts.find(a=>a.track_id===threat.track_id)?.direction_hint && (
              <div className="risk-detail-row">
                <span className="lbl">Direction</span>
                <span className="val accent">{frame.alerts.find(a=>a.track_id===threat.track_id)?.direction_hint}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Alerts */}
      <div className="alerts-card">
        <div className="panel-hdr">
          <div className="panel-title">⚠ Active Alerts</div>
          {alerts.length>0 && <span className="count-badge">{alerts.length}</span>}
        </div>
        <div className="alerts-body">
          {sortedAlerts.length===0 ? (
            <div className="alerts-clear">
              <div className="alerts-clear-icon">🔔</div>
              <div>No alerts</div>
              <div style={{fontSize:9,color:'var(--text-dim)'}}>System operating normally</div>
            </div>
          ) : sortedAlerts.map((a,i) => (
            <div key={i} className={`alert-item-new ${a.risk_state}`}>
              <span className={`alert-level-badge ${a.risk_state}`}>{a.risk_state.toUpperCase()}</span>
              <div className="alert-msg-new">{a.message}</div>
              <div className="alert-meta-new">
                <span>Track #{a.track_id}</span>
                {a.direction_hint && <span>📍 {a.direction_hint}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Tracks */}
      <div className="tracks-card">
        <div className="panel-hdr">
          <div className="panel-title">⊛ Active Tracks</div>
          <span className="count-badge">{tracks.length}</span>
        </div>
        <div className="tracks-body">
          {tracks.length===0 ? (
            <div className="empty-state" style={{padding:'8px 2px'}}>No active tracks</div>
          ) : tracks.map((t: Track) => {
            const speed  = Math.hypot(t.velocity_xy[0], t.velocity_xy[1]);
            const dist   = Math.hypot(t.position_xy[0], t.position_xy[1]);
            const closing= t.velocity_xy[1] < -0.2;
            return (
              <div key={t.track_id} className="track-item-new">
                <div className="track-top">
                  <div className="track-label">
                    <span className="track-cls-icon">{CLS_ICON[t.cls]??'◆'}</span>
                    <span className="track-cls-name">{CLS_LABEL[t.cls]??t.cls}</span>
                    <span className="track-id-badge">#{t.track_id}</span>
                  </div>
                  {closing
                    ? <span className="track-closing">Closing</span>
                    : <span className="track-static">Static</span>
                  }
                </div>
                <div className="track-pos">
                  <span><b>{dist.toFixed(1)}</b> m</span>
                  <span><b>{speed.toFixed(1)}</b> m/s</span>
                  <span style={{color:'var(--text-dim)'}}>{t.confidence>0.7?'High':'Low'} conf</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Footer
function Footer({ frame }: { frame: LiveFrame|null }) {
  const lat = frame?.latency ?? null;
  const totalWarn = lat!=null && lat.total > 100;

  function Chip({ label, value, unit, warn }: {label:string;value:string;unit?:string;warn?:boolean}) {
    return (
      <div className="metric-chip">
        <span className="metric-chip-label">{label}</span>
        <span className={`metric-chip-value${warn?' warn':''}`}>{value}</span>
        {unit && <span className="metric-chip-unit">{unit}</span>}
      </div>
    );
  }

  return (
    <div className="dash-footer">
      <div className="footer-section">
        <span className="footer-section-label">Performance Metrics</span>
        <Chip label="Perception" value={lat?lat.perception.toFixed(1):'—'} unit="ms"/>
        <Chip label="Fusion"     value={lat?lat.fusion.toFixed(1):'—'}     unit="ms"/>
        <Chip label="Tracking"   value={lat?lat.tracking.toFixed(1):'—'}   unit="ms"/>
        <Chip label="Risk"       value={lat?lat.risk.toFixed(1):'—'}       unit="ms"/>
        <Chip label="Total"      value={lat?lat.total.toFixed(1):'—'}      unit="ms" warn={totalWarn}/>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------
export default function App() {
  const { data, connectionState, lastUpdate, reconnect } = useLivePipeline();
  
  const currentRisk = data?.highest_risk ?? 'safe';
  const { soundEnabled, toggleSound } = useWarningSound(currentRisk);

  const offline = connectionState==='disconnected'||connectionState==='error';

  // Sensor mode
  const [sensorMode, setSensorMode] = useState<SensorModeResponse|null>(null);
  useEffect(() => {
    fetch(`${HTTP_BASE}/api/config/mode`)
      .then(r=>r.json())
      .then((d:SensorModeResponse)=>setSensorMode(d))
      .catch(()=>{});
  },[]);

  // Scenarios
  const [scenarios,     setScenarios]     = useState<ScenarioInfo[]>([]);
  const [simError,      setSimError]      = useState<string|null>(null);

  useEffect(() => {
    fetch(`${HTTP_BASE}/api/scenarios`)
      .then(r=>r.json())
      .then(d=>setScenarios(d.scenarios??[]))
      .catch(()=>{});
  },[]);

  const currentScenario = data?.scenario ?? 'SAFE';

  const selectScenario = useCallback(async (name: string) => {
    setSimError(null);
    try {
      const resp = await fetch(`${HTTP_BASE}/api/scenario`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({scenario:name}),
      });
      if (!resp.ok) {
        const b = await resp.json().catch(()=>({}));
        setSimError(b.detail??`HTTP ${resp.status}`);
      }
    } catch { setSimError('Network error'); }
  },[]);

  // Check if any object is within 40 meters AND we're in COLLISION_DEMO mode
  const dangerousProximity = (currentScenario === 'COLLISION_DEMO') && (data?.tracks.some(track => {
    const distance = Math.hypot(track.position_xy[0], track.position_xy[1]);
    return distance <= 40;
  }) ?? false);

  return (
    <>
      <div className="dash-root">
        {/* Header */}
        <Header
          frame={data}
          connState={connectionState}
          sensorMode={sensorMode}
          lastUpdate={lastUpdate}
          onReconnect={reconnect}
          currentScenario={currentScenario}
          scenarios={scenarios}
          onSelectScenario={selectScenario}
          soundEnabled={soundEnabled}
          onToggleSound={toggleSound}
        />

        {/* Main Body */}
        <div className="dash-body-new">
          {/* Simulation Mode Badge */}
          <SimulationBadge />

          {/* Main Perception Row - All Three Panels Side by Side */}
          <div className="perception-row-three">
            <ThermalPerceptionPanel
              detections={data?.thermal_detections ?? []}
              quality={data?.thermal_quality ?? 0}
              frameNumber={data?.frame_number ?? null}
            />
            <RadarPerceptionPanel
              clusters={data?.radar_clusters ?? []}
              quality={data?.radar_quality ?? 0}
              frameNumber={data?.frame_number ?? null}
            />
            <VehicleTrajectoryPanel
              tracks={data?.tracks ?? []}
              risks={data?.risks ?? []}
              frameNumber={data?.frame_number ?? null}
            />
          </div>

          {/* Bottom Cards Row */}
          <BottomCards frame={data} />
        </div>

        {/* Footer */}
        <Footer frame={data}/>
      </div>

      {/* Sim error toast */}
      {simError && (
        <div style={{
          position:'fixed',bottom:50,left:'50%',transform:'translateX(-50%)',
          background:'var(--critical-bg)',border:'1px solid var(--critical-border)',
          borderRadius:'var(--r)',padding:'6px 14px',
          fontFamily:'var(--font-mono)',fontSize:11,color:'var(--critical)',
          zIndex:200,
        }}>
          {simError}
        </div>
      )}

      {/* Disconnected overlay */}
      {offline && (
        <div className="disconnected-overlay">
          <div className="dc-title">⚠ BACKEND DISCONNECTED</div>
          <div className="dc-sub">
            {connectionState==='error'
              ? 'Connection error — check that the backend is running on port 8000.'
              : 'Lost connection to MINEXIS backend.'}
          </div>
          <button className="dc-btn" onClick={reconnect}>RECONNECT</button>
        </div>
      )}

      {/* Collision Risk Popup — appears when any object is within 40m */}
      {dangerousProximity && data && (
        <div className="collision-popup-overlay">
          <div className="collision-popup">
            <div className="collision-icon-wrapper">
              <div className="collision-icon">⬟</div>
            </div>
            <div className="collision-title">COLLISION RISK</div>
            <div className="collision-subtitle">Object within critical proximity</div>
            
            <div className="collision-details">
              {data.tracks
                .filter(t => Math.hypot(t.position_xy[0], t.position_xy[1]) <= 40)
                .map(track => {
                  const distance = Math.hypot(track.position_xy[0], track.position_xy[1]);
                  const risk = data.risks.find(r => r.track_id === track.track_id);
                  return (
                    <div key={track.track_id} className="collision-track-item">
                      <div className="collision-track-header">
                        <span className="collision-track-id">TRACK #{track.track_id}</span>
                        <span className="collision-track-class">{CLS_LABEL[track.cls] ?? track.cls}</span>
                      </div>
                      <div className="collision-track-info">
                        <div className="collision-info-row">
                          <span className="collision-info-label">Distance:</span>
                          <span className="collision-info-value">{distance.toFixed(1)} m</span>
                        </div>
                        {risk?.ttc_s != null && (
                          <div className="collision-info-row">
                            <span className="collision-info-label">TTC:</span>
                            <span className="collision-info-value collision-ttc">{risk.ttc_s.toFixed(1)} s</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>

            <div className="collision-action-text">⚠ TAKE IMMEDIATE ACTION ⚠</div>
          </div>
        </div>
      )}
    </>
  );
}
