/**
 * ThermalPerceptionPanel — Square thermal perception visualization.
 *
 * Displays thermal detections in a square 1:1 aspect ratio canvas with:
 * - Webcam-based simulated thermal imagery (heatmap palette)
 * - Detection bounding boxes overlaid
 * - Class labels and confidence when available
 * - Clear "SIMULATED" badge
 *
 * All data from the actual simulator — no fabricated objects.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { ThermalDetection } from '../types';

// Thermal color palette (blue → red → yellow gradient)
const PALETTE: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    let r = 0, g = 0, b = 0;
    if (t < 0.2)       { const s = t/0.2;          r=Math.round(20*s);      g=0;                    b=Math.round(80*s); }
    else if (t < 0.45) { const s=(t-0.2)/0.25;     r=Math.round(20+160*s); g=0;                    b=Math.round(80-70*s); }
    else if (t < 0.65) { const s=(t-0.45)/0.20;    r=Math.round(180+60*s); g=Math.round(60*s);     b=10; }
    else if (t < 0.85) { const s=(t-0.65)/0.20;    r=240;                  g=Math.round(60+150*s); b=Math.round(10+20*s); }
    else               { const s=(t-0.85)/0.15;    r=Math.round(240+15*s); g=Math.round(210+45*s); b=Math.round(30+195*s); }
    lut[i*3]  =Math.min(255,r);
    lut[i*3+1]=Math.min(255,g);
    lut[i*3+2]=Math.min(255,b);
  }
  return lut;
})();

type CamState = 'idle'|'requesting'|'active'|'denied'|'error'|'stopped';

const CLS_LABEL: Record<string, string> = {
  person: 'Person',
  vehicle: 'Vehicle',
  large_obstacle: 'Obstacle',
  unknown: 'Object',
};

interface Props {
  detections: ThermalDetection[];
  quality: number;
  frameNumber: number | null;
}

export function ThermalPerceptionPanel({ detections, quality, frameNumber }: Props) {
  const videoRef     = useRef<HTMLVideoElement>(null);
  const canvasRef    = useRef<HTMLCanvasElement>(null);
  const overlayRef   = useRef<HTMLCanvasElement>(null);
  const streamRef    = useRef<MediaStream | null>(null);
  const rafRef       = useRef<number | null>(null);
  const lastRef      = useRef<number>(0);
  const offRef       = useRef<HTMLCanvasElement | null>(null);
  const scanLineRef  = useRef<number>(0); // For scan line animation
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
    // Scanline effect
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

  // Draw detection overlays with spotlight effect and animated scan line
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay || cam !== 'active') return;
    const ctx = overlay.getContext('2d');
    if (!ctx) return;
    
    let animationFrameId: number;
    
    const animate = () => {
      ctx.clearRect(0, 0, overlay.width, overlay.height);
      
      // Update scan line position
      scanLineRef.current = (scanLineRef.current + 2) % overlay.height;
      
      detections.forEach((det, idx) => {
        const [x0, y0, x1, y1] = det.box_xyxy;
        const w = x1 - x0;
        const h = y1 - y0;
        const cx = (x0 + x1) / 2;
        const cy = (y0 + y1) / 2;
        
        // Determine color based on class
        let spotlightColor = 'rgba(167, 139, 250, 1)'; // Default purple
        let glowColor = 'rgba(167, 139, 250, 0.3)';
        
        if (det.cls === 'person') {
          spotlightColor = 'rgba(34, 197, 94, 1)'; // Green for person
          glowColor = 'rgba(34, 197, 94, 0.3)';
        } else if (det.cls === 'vehicle') {
          spotlightColor = 'rgba(245, 158, 11, 1)'; // Amber for vehicle
          glowColor = 'rgba(245, 158, 11, 0.3)';
        } else if (det.cls === 'large_obstacle') {
          spotlightColor = 'rgba(239, 68, 68, 1)'; // Red for obstacle
          glowColor = 'rgba(239, 68, 68, 0.3)';
        }
        
        // Outer glow effect (spotlight)
        ctx.save();
        ctx.shadowBlur = 20;
        ctx.shadowColor = glowColor;
        ctx.strokeStyle = glowColor;
        ctx.lineWidth = 8;
        ctx.strokeRect(x0 - 4, y0 - 4, w + 8, h + 8);
        ctx.restore();
        
        // Main spotlight square
        ctx.strokeStyle = spotlightColor;
        ctx.lineWidth = 3;
        ctx.strokeRect(x0, y0, w, h);
        
        // Inner highlight line (gives depth)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x0 + 2, y0 + 2, w - 4, h - 4);
        
        // Corner accents (animated feel)
        const cornerLen = Math.min(16, w/3.5, h/3.5);
        ctx.strokeStyle = spotlightColor;
        ctx.lineWidth = 4;
        
        // Top-left corner
        ctx.beginPath();
        ctx.moveTo(x0, y0 + cornerLen);
        ctx.lineTo(x0, y0);
        ctx.lineTo(x0 + cornerLen, y0);
        ctx.stroke();
        
        // Top-right corner
        ctx.beginPath();
        ctx.moveTo(x1 - cornerLen, y0);
        ctx.lineTo(x1, y0);
        ctx.lineTo(x1, y0 + cornerLen);
        ctx.stroke();
        
        // Bottom-left corner
        ctx.beginPath();
        ctx.moveTo(x0, y1 - cornerLen);
        ctx.lineTo(x0, y1);
        ctx.lineTo(x0 + cornerLen, y1);
        ctx.stroke();
        
        // Bottom-right corner
        ctx.beginPath();
        ctx.moveTo(x1 - cornerLen, y1);
        ctx.lineTo(x1, y1);
        ctx.lineTo(x1, y1 - cornerLen);
        ctx.stroke();
        
        // Crosshair at center (for precision targeting)
        const crossSize = 8;
        ctx.strokeStyle = spotlightColor;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx - crossSize, cy);
        ctx.lineTo(cx + crossSize, cy);
        ctx.moveTo(cx, cy - crossSize);
        ctx.lineTo(cx, cy + crossSize);
        ctx.stroke();
        
        // Center dot
        ctx.fillStyle = spotlightColor;
        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fill();
        
        // Label background with glow
        const label = `${CLS_LABEL[det.cls] ?? det.cls}`;
        const confText = det.confidence >= 0 ? ` ${(det.confidence * 100).toFixed(0)}%` : '';
        const text = label + confText;
        ctx.font = 'bold 12px monospace';
        const metrics = ctx.measureText(text);
        const textW = metrics.width + 12;
        const textH = 18;
        
        // Label glow
        ctx.save();
        ctx.shadowBlur = 10;
        ctx.shadowColor = glowColor;
        ctx.fillStyle = spotlightColor;
        ctx.fillRect(x0 - 1, y0 - textH - 4, textW + 2, textH + 2);
        ctx.restore();
        
        // Label background
        ctx.fillStyle = spotlightColor;
        ctx.fillRect(x0, y0 - textH - 2, textW, textH);
        
        // Label text
        ctx.fillStyle = '#000';
        ctx.font = 'bold 12px monospace';
        ctx.textBaseline = 'top';
        ctx.fillText(text, x0 + 6, y0 - textH + 1);
        
        // Target ID badge (bottom left)
        const idBadgeW = 32;
        const idBadgeH = 16;
        
        // Badge glow
        ctx.save();
        ctx.shadowBlur = 8;
        ctx.shadowColor = glowColor;
        ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        ctx.fillRect(x0 - 1, y1 - idBadgeH + 1, idBadgeW + 2, idBadgeH + 2);
        ctx.restore();
        
        // Badge background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
        ctx.fillRect(x0, y1 - idBadgeH + 2, idBadgeW, idBadgeH);
        
        // Badge border
        ctx.strokeStyle = spotlightColor;
        ctx.lineWidth = 2;
        ctx.strokeRect(x0, y1 - idBadgeH + 2, idBadgeW, idBadgeH);
        
        // Target ID text
        ctx.fillStyle = spotlightColor;
        ctx.font = 'bold 11px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`T${idx + 1}`, x0 + idBadgeW / 2, y1 - idBadgeH / 2 + 2);
        ctx.textAlign = 'left'; // Reset
        
        // Distance indicator line (if multiple objects, show separation)
        if (detections.length > 1) {
          ctx.strokeStyle = `${spotlightColor.replace('1)', '0.3)')}`;
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(overlay.width / 2, overlay.height / 2);
          ctx.stroke();
          ctx.setLineDash([]); // Reset
        }
      });
      
      // Draw animated scan line
      const scanY = scanLineRef.current;
      const gradient = ctx.createLinearGradient(0, scanY - 20, 0, scanY + 20);
      gradient.addColorStop(0, 'rgba(56, 189, 248, 0)');
      gradient.addColorStop(0.5, 'rgba(56, 189, 248, 0.5)');
      gradient.addColorStop(1, 'rgba(56, 189, 248, 0)');
      
      ctx.fillStyle = gradient;
      ctx.fillRect(0, scanY - 20, overlay.width, 40);
      
      // Continue animation
      animationFrameId = requestAnimationFrame(animate);
    };
    
    animate();
    
    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, [detections, cam]);

  const camActive  = cam === 'active';
  const camFailed  = cam === 'denied' || cam === 'error';
  const qualityColor = quality >= 0.7 ? '#22c55e' : quality >= 0.4 ? '#f59e0b' : '#ef4444';
  const qualityStatus = quality >= 0.7 ? 'ACTIVE' : quality >= 0.4 ? 'DEGRADED' : 'POOR';

  return (
    <div className="perception-panel">
      <video ref={videoRef} muted playsInline aria-hidden style={{display:'none'}}/>
      
      <div className="perception-header">
        <div className="perception-title">
          <span className="perception-icon">⬤</span>
          <span>THERMAL PERCEPTION</span>
        </div>
        <div className="perception-meta">
          <span className="perception-status" style={{color: qualityColor}}>{qualityStatus}</span>
          <span className="perception-sep">|</span>
          <span className="perception-frame">F{frameNumber ?? '—'}</span>
        </div>
      </div>

      <div className="perception-body">
        {camActive ? (
          <div className="thermal-scene-wrapper">
            <canvas
              ref={canvasRef}
              className="thermal-scene-canvas"
              width={320}
              height={320}
              aria-label="Simulated thermal visualization"
            />
            <canvas
              ref={overlayRef}
              className="thermal-scene-overlay"
              width={320}
              height={320}
            />
            <div className="thermal-scene-badge">SIMULATED</div>
            <div className="thermal-scene-info">
              <div className="thermal-info-row">
                <span className="thermal-info-label">DETECTIONS</span>
                <span className="thermal-info-value">{detections.length}</span>
              </div>
              <div className="thermal-info-row">
                <span className="thermal-info-label">QUALITY</span>
                <span className="thermal-info-value" style={{color: qualityColor}}>
                  {(quality * 100).toFixed(0)}%
                </span>
              </div>
            </div>
            {!camActive && (
              <div className="thermal-scene-controls">
                <button className="thermal-scene-btn" onClick={stop}>STOP CAM</button>
              </div>
            )}
          </div>
        ) : (
          <div className="perception-fallback">
            <div className="perception-fallback-icon">⬡</div>
            <div className="perception-fallback-title">
              {camFailed ? 'THERMAL UNAVAILABLE' : cam==='stopped' ? 'THERMAL STOPPED' : 'INITIALIZING...'}
            </div>
            <div className="perception-fallback-subtitle">
              {camFailed ? 'Synthetic pipeline active' : cam==='stopped' ? 'Webcam stopped' : 'Preparing sensor...'}
            </div>
            {(camFailed || cam==='stopped') && (
              <button className="perception-fallback-btn" onClick={start}>
                {camFailed ? 'RETRY' : 'START CAMERA'}
              </button>
            )}
          </div>
        )}
      </div>

      <div className="perception-footer">
        <div className="perception-legend-item">
          <span style={{color:'rgba(34, 197, 94, 1)',fontSize:10}}>■</span>
          <span>Person</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'rgba(245, 158, 11, 1)',fontSize:10}}>■</span>
          <span>Vehicle</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'rgba(239, 68, 68, 1)',fontSize:10}}>■</span>
          <span>Obstacle</span>
        </div>
        <div className="perception-legend-item">
          <span style={{color:'rgba(167, 139, 250, 1)',fontSize:10}}>■</span>
          <span>Unknown</span>
        </div>
        <div className="perception-legend-item" style={{marginLeft:'auto'}}>
          <span>{detections.length} Detected</span>
        </div>
      </div>
    </div>
  );
}
