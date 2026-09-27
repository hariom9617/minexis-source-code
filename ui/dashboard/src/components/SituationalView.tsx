/**
 * SituationalView — Combined radar + thermal situational awareness panel.
 *
 * Tabs: Radar+Thermal | Radar | Thermal
 * Left half: enhanced radar SVG (from existing RadarView logic)
 * Right half: ThermalView canvas (existing logic, slimmed presentation)
 *
 * All data comes from the existing pipeline — nothing fabricated.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { RadarCluster, ThermalDetection, Track } from '../types';

// Re-use palette from ThermalView
const PALETTE: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    let r = 0, g = 0, b = 0;
    if (t < 0.2)       { const s = t/0.2;          r=Math.round(20*s);      g=0;                    b=Math.round(80*s); }
    else if (t < 0.45) { const s=(t-0.2)/0.25;     r=Math.round(20+160*s); g=0;                    b=Math.round(80-70*s); }
    else if (t < 0.65) { const s=(t-0.45)/0.20;    r=Math.round(180+60*s); g=Math.round(60*s);     b=10; }
    else if (t < 0.85) { const s=(t-0.65)/0.20;    r=240;                  g=Math.round(60+150*s); b=Math.round(10+20*s); }
    else               { const s=(t-0.85)/0.15;     r=Math.round(240+15*s);g=Math.round(210+45*s); b=Math.round(30+195*s); }
    lut[i*3]  =Math.min(255,r);
    lut[i*3+1]=Math.min(255,g);
    lut[i*3+2]=Math.min(255,b);
  }
  return lut;
})();

// ── Radar drawing helpers ──────────────────────────────────────────────────
const RADAR_SIZE   = 300;
const CX = RADAR_SIZE / 2, CY = RADAR_SIZE / 2;
const MAX_RANGE_M  = 60;
const R_MAX        = RADAR_SIZE / 2 - 14;
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

// ── Props ──────────────────────────────────────────────────────────────────
interface Props {
  clusters:   RadarCluster[];
  detections: ThermalDetection[];
  tracks:     Track[];
}

type Tab = 'both' | 'radar' | 'thermal';

// ── Camera hook (same logic as ThermalView, minimal) ──────────────────────
type CamState = 'idle'|'requesting'|'active'|'denied'|'error'|'stopped';

function useThermalCam() {
  const videoRef     = useRef<HTMLVideoElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const streamRef    = useRef<MediaStream|null>(null);
  const rafRef       = useRef<number|null>(null);
  const lastRef      = useRef<number>(0);
  const offRef       = useRef<HTMLCanvasElement|null>(null);
  const [cam, setCam]= useState<CamState>('idle');

  const renderLoop = useCallback((now: number) => {
    rafRef.current = requestAnimationFrame(renderLoop);
    if (now - lastRef.current < 50) return; // ~20fps
    lastRef.current = now;
    const vid = videoRef.current, cvs = canvasRef.current;
    if (!vid || !cvs || vid.readyState < 2) return;
    const W = cvs.width, H = cvs.height;
    if (!offRef.current) offRef.current = document.createElement('canvas');
    const off = offRef.current; off.width=W; off.height=H;
    const oc = off.getContext('2d',{willReadFrequently:true}); if(!oc) return;
    oc.save(); oc.translate(W,0); oc.scale(-1,1); oc.drawImage(vid,0,0,W,H); oc.restore();
    const img = oc.getImageData(0,0,W,H), src = img.data;
    const out = new Uint8ClampedArray(W*H*4);
    for (let p=0;p<W*H;p++) {
      const b=p*4, lum=Math.min(255,Math.max(0,(0.299*src[b]+0.587*src[b+1]+0.114*src[b+2])*1.25-10));
      const idx=Math.round(lum)*3;
      out[b]=PALETTE[idx]; out[b+1]=PALETTE[idx+1]; out[b+2]=PALETTE[idx+2]; out[b+3]=255;
    }
    const ctx = cvs.getContext('2d'); if(!ctx) return;
    ctx.putImageData(new ImageData(out,W,H),0,0);
    ctx.fillStyle='rgba(0,0,0,0.05)';
    for(let y=0;y<H;y+=3) ctx.fillRect(0,y,W,1);
  },[]);

  const start = useCallback(async () => {
    if (cam==='requesting') return;
    setCam('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video:{facingMode:'user',width:{ideal:320},height:{ideal:240}}, audio:false
      });
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject=stream; await videoRef.current.play(); }
      setCam('active');
      rafRef.current = requestAnimationFrame(renderLoop);
    } catch(e:unknown) {
      const n=(e as Error)?.name??'';
      setCam(n==='NotAllowedError'||n==='PermissionDeniedError' ? 'denied' : 'error');
    }
  },[cam, renderLoop]);

  const stop = useCallback(() => {
    if (rafRef.current!==null) { cancelAnimationFrame(rafRef.current); rafRef.current=null; }
    streamRef.current?.getTracks().forEach(t=>t.stop()); streamRef.current=null;
    if (videoRef.current) videoRef.current.srcObject=null;
    setCam('stopped');
  },[]);

  useEffect(() => {
    start();
    return () => {
      if (rafRef.current!==null) cancelAnimationFrame(rafRef.current);
      streamRef.current?.getTracks().forEach(t=>t.stop());
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);

  return { videoRef, canvasRef, cam, start, stop };
}

// ── Main component ─────────────────────────────────────────────────────────
export function SituationalView({ clusters, detections, tracks }: Props) {
  const [tab, setTab] = useState<Tab>('both');
  const { videoRef, canvasRef, cam, start, stop } = useThermalCam();

  const showRadar   = tab === 'both' || tab === 'radar';
  const showThermal = tab === 'both' || tab === 'thermal';

  const camActive  = cam === 'active';
  const camFailed  = cam === 'denied' || cam === 'error';

  return (
    <div className="sv-panel">
      {/* Header */}
      <div className="sv-header">
        <div className="sv-title">
          <span>◈</span>
          <span>Situational View</span>
        </div>
        <div className="sv-tabs">
          {(['both','radar','thermal'] as Tab[]).map(t => (
            <button
              key={t}
              className={`sv-tab${tab===t?' active':''}`}
              onClick={() => setTab(t)}
            >
              {t==='both'?'Radar + Thermal':t==='radar'?'Radar':'Thermal'}
            </button>
          ))}
        </div>
        <div style={{display:'flex',gap:6,alignItems:'center'}}>
          {camActive && (
            <button
              className="sv-tab"
              onClick={stop}
              style={{fontSize:9,padding:'2px 8px',color:'var(--critical)',borderColor:'var(--critical-border)'}}
            >
              STOP CAM
            </button>
          )}
          {(camFailed||cam==='stopped') && (
            <button className="sv-tab" onClick={()=>{start()}} style={{fontSize:9,padding:'2px 8px'}}>
              {camFailed?'RETRY CAM':'START CAM'}
            </button>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="sv-body">
        {/* Radar half */}
        {showRadar && (
          <div className="sv-half" style={{flex: tab==='radar' ? 2 : 1}}>
            <div className="sv-radar-wrap">
              <svg
                className="sv-radar-svg"
                viewBox={`0 0 ${RADAR_SIZE} ${RADAR_SIZE}`}
                width="100%"
                height="100%"
                style={{maxWidth: RADAR_SIZE, maxHeight: RADAR_SIZE}}
                aria-label="Radar situational view"
              >
                {/* Range rings */}
                {RING_RANGES.map(r_m => {
                  const r_px = toRadius(r_m);
                  return (
                    <g key={r_m}>
                      <circle cx={CX} cy={CY} r={r_px} fill="none" stroke="rgba(56,189,248,0.10)" strokeWidth={1}/>
                      <text x={CX+3} y={CY-r_px+10} fontSize={8} fill="rgba(56,189,248,0.30)" fontFamily="monospace">{r_m}m</text>
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
                      stroke="rgba(56,189,248,0.09)" strokeWidth={1}
                      strokeDasharray={deg===0?'4 3':undefined}
                    />
                  );
                })}
                {/* Compass N/S/E/W */}
                <text x={CX-3} y={14}  fontSize={9} fill="rgba(56,189,248,0.4)" fontFamily="monospace">N</text>
                <text x={CX-3} y={RADAR_SIZE-4} fontSize={9} fill="rgba(56,189,248,0.25)" fontFamily="monospace">S</text>
                <text x={8}    y={CY+4} fontSize={9} fill="rgba(56,189,248,0.25)" fontFamily="monospace">W</text>
                <text x={RADAR_SIZE-14} y={CY+4} fontSize={9} fill="rgba(56,189,248,0.25)" fontFamily="monospace">E</text>
                {/* Clusters */}
                {clusters.map((cl,i) => {
                  const [sx,sy] = polarToSvg(cl.range_m, cl.azimuth_deg);
                  const col     = clusterColor(cl.doppler_mps);
                  const dotR    = 4 + cl.point_count * 1.2 + cl.persistence * 2;
                  return (
                    <g key={i}>
                      <circle cx={sx} cy={sy} r={dotR+5} fill={col} opacity={0.10}/>
                      <circle cx={sx} cy={sy} r={dotR}   fill={col} opacity={0.85}/>
                      {cl.doppler_mps > 0.5 && (
                        <line x1={sx} y1={sy} x2={sx} y2={sy+Math.min(cl.doppler_mps*3,16)}
                          stroke={col} strokeWidth={1.5} opacity={0.7} strokeLinecap="round"/>
                      )}
                      <text x={sx+dotR+3} y={sy+4} fontSize={9} fill="rgba(232,232,240,0.6)" fontFamily="monospace">
                        {cl.range_m.toFixed(0)}m
                      </text>
                    </g>
                  );
                })}
                {/* Thermal detection overlays (azimuth-only, approximate) */}
                {detections.map((d,i) => {
                  // map box centre pixel to azimuth (linear: width=320, fov=50°)
                  const cx_px = (d.box_xyxy[0]+d.box_xyxy[2])/2;
                  const az = ((cx_px/320)-0.5)*50;
                  const approxRange = 20; // no depth from thermal; place at midfield
                  const [sx,sy] = polarToSvg(approxRange, az);
                  return (
                    <g key={`det-${i}`}>
                      <rect x={sx-6} y={sy-6} width={12} height={12}
                        fill="none" stroke="rgba(167,139,250,0.7)" strokeWidth={1.5}
                        rx={2}
                      />
                      <text x={sx} y={sy+18} fontSize={8} textAnchor="middle"
                        fill="rgba(167,139,250,0.6)" fontFamily="monospace">
                        {d.cls}
                      </text>
                    </g>
                  );
                })}
                {/* Own vehicle */}
                <polygon
                  points={`${CX},${CY-10} ${CX-7},${CY+8} ${CX+7},${CY+8}`}
                  fill="rgba(56,189,248,0.90)"
                  stroke="#060c18" strokeWidth={1.5}
                />
                <text x={CX} y={CY+20} fontSize={8} textAnchor="middle"
                  fill="rgba(56,189,248,0.5)" fontFamily="monospace">Own Vehicle</text>
                {/* Outer ring */}
                <circle cx={CX} cy={CY} r={R_MAX} fill="none" stroke="rgba(56,189,248,0.18)" strokeWidth={1}/>
              </svg>
            </div>
          </div>
        )}

        {/* Thermal half */}
        {showThermal && (
          <div className="sv-half" style={{flex: tab==='thermal' ? 2 : 1}}>
            <video ref={videoRef} muted playsInline aria-hidden style={{display:'none'}}/>
            {camActive ? (
              <div className="sv-thermal-wrap">
                <canvas
                  ref={canvasRef}
                  className="sv-thermal-canvas"
                  width={320} height={240}
                  aria-label="Simulated thermal visualization"
                />
                <div className="sv-thermal-label">WEBCAM SOURCE · SIMULATED THERMAL</div>
              </div>
            ) : (
              <div className="sv-thermal-fallback">
                <div className="sv-thermal-fallback-icon">⬡</div>
                <div style={{fontSize:10,color:'var(--thermal)',fontFamily:'var(--font-mono)',letterSpacing:'1px'}}>
                  {camFailed ? 'THERMAL UNAVAILABLE' : cam==='stopped' ? 'THERMAL STOPPED' : 'INITIALISING…'}
                </div>
                <div style={{fontSize:9,color:'var(--text-dim)',marginTop:3}}>
                  {camFailed ? 'Synthetic pipeline active' : ''}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="sv-legend">
        <span><span style={{color:'#38bdf8',fontSize:10}}>●</span> Static</span>
        <span><span style={{color:'#ef4444',fontSize:10}}>●</span> Closing</span>
        <span><span style={{color:'rgba(167,139,250,0.8)',fontSize:10}}>■</span> Thermal Det.</span>
        <span>▲ Own Vehicle</span>
        {tracks.length > 0 && (
          <span style={{marginLeft:'auto',color:'var(--accent)'}}>
            {tracks.length} track{tracks.length!==1?'s':''} active
          </span>
        )}
      </div>
    </div>
  );
}
