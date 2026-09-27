/**
 * ThermalView — Webcam-sourced pseudo-thermal visualization panel.
 *
 * ── IMPORTANT HONESTY NOTICE ──────────────────────────────────────────────
 * This component uses the laptop's RGB webcam, NOT a thermal camera.
 * It applies a colour-mapping filter to resemble a thermal heatmap for
 * PRESENTATION PURPOSES ONLY.
 *
 * The panel is labelled "SIMULATED THERMAL — WEBCAM DEMO" and must never
 * be described as real thermal data.
 *
 * The actual MINEXIS thermal pipeline (ThermalBranch → AdaptiveFusion →
 * Tracker → RiskEngine) continues to use the synthetic thermal source
 * from the backend.  This component is COMPLETELY INDEPENDENT of the AI
 * pipeline — webcam frames are never sent to the backend.
 * ──────────────────────────────────────────────────────────────────────────
 *
 * Performance design
 * ------------------
 * - Video element and canvas are accessed via refs; no React state per frame.
 * - requestAnimationFrame drives the render loop at the browser's natural
 *   pace, throttled internally to ~20 fps to keep CPU load low.
 * - All frame processing (greyscale → palette mapping) is done on a single
 *   offscreen CanvasRenderingContext2D.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Pseudo-thermal palette
// Sampled from a standard iron/inferno heatmap:
// index 0 = darkest/coolest (black-blue), index 255 = brightest/hottest (white-yellow)
// ---------------------------------------------------------------------------

const PALETTE: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 3);  // R,G,B per entry
  for (let i = 0; i < 256; i++) {
    const t = i / 255;
    // Iron-like colour map: black → purple → red → orange → yellow → white
    let r: number, g: number, b: number;
    if (t < 0.2) {
      // black → deep purple
      const s = t / 0.2;
      r = Math.round(20  * s);
      g = Math.round(0);
      b = Math.round(80  * s);
    } else if (t < 0.45) {
      // deep purple → dark red
      const s = (t - 0.2) / 0.25;
      r = Math.round(20  + 160 * s);
      g = Math.round(0);
      b = Math.round(80  - 70  * s);
    } else if (t < 0.65) {
      // dark red → orange
      const s = (t - 0.45) / 0.20;
      r = Math.round(180 + 60  * s);
      g = Math.round(60  * s);
      b = Math.round(10);
    } else if (t < 0.85) {
      // orange → bright yellow
      const s = (t - 0.65) / 0.20;
      r = Math.round(240);
      g = Math.round(60  + 150 * s);
      b = Math.round(10  + 20  * s);
    } else {
      // bright yellow → near-white
      const s = (t - 0.85) / 0.15;
      r = Math.round(240 + 15  * s);
      g = Math.round(210 + 45  * s);
      b = Math.round(30  + 195 * s);
    }
    lut[i * 3 + 0] = Math.min(255, r);
    lut[i * 3 + 1] = Math.min(255, g);
    lut[i * 3 + 2] = Math.min(255, b);
  }
  return lut;
})();

type CameraState = 'idle' | 'requesting' | 'active' | 'denied' | 'error' | 'stopped';

const TARGET_FPS = 20;
const FRAME_MS   = 1000 / TARGET_FPS;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ThermalView() {
  const videoRef    = useRef<HTMLVideoElement>(null);
  const canvasRef   = useRef<HTMLCanvasElement>(null);
  const streamRef   = useRef<MediaStream | null>(null);
  const rafRef      = useRef<number | null>(null);
  const lastDrawRef = useRef<number>(0);
  const offscreenRef = useRef<HTMLCanvasElement | null>(null);

  const [camState, setCamState] = useState<CameraState>('idle');

  // ── Frame rendering loop ────────────────────────────────────────────────
  const renderLoop = useCallback((now: number) => {
    rafRef.current = requestAnimationFrame(renderLoop);

    if (now - lastDrawRef.current < FRAME_MS) return;
    lastDrawRef.current = now;

    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return;

    const W = canvas.width;
    const H = canvas.height;

    // Ensure offscreen canvas matches
    if (!offscreenRef.current) {
      offscreenRef.current = document.createElement('canvas');
    }
    const off = offscreenRef.current;
    off.width  = W;
    off.height = H;
    const octx = off.getContext('2d', { willReadFrequently: true });
    if (!octx) return;

    // Draw video frame to offscreen canvas (mirrored for natural feel)
    octx.save();
    octx.translate(W, 0);
    octx.scale(-1, 1);
    octx.drawImage(video, 0, 0, W, H);
    octx.restore();

    // Read pixel data
    const imgData = octx.getImageData(0, 0, W, H);
    const src     = imgData.data;

    // Build thermal output in-place
    const out = new Uint8ClampedArray(W * H * 4);
    for (let p = 0; p < W * H; p++) {
      const base = p * 4;
      const r = src[base];
      const g = src[base + 1];
      const b = src[base + 2];

      // Luminance (BT.601)
      let lum = (0.299 * r + 0.587 * g + 0.114 * b);

      // Mild contrast stretch: push midtones out
      lum = Math.min(255, lum * 1.25 - 10);

      const idx = Math.max(0, Math.min(255, Math.round(lum))) * 3;
      out[base]     = PALETTE[idx];
      out[base + 1] = PALETTE[idx + 1];
      out[base + 2] = PALETTE[idx + 2];
      out[base + 3] = 255;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const outData = new ImageData(out, W, H);
    ctx.putImageData(outData, 0, 0);

    // Overlay scanline texture for authenticity
    ctx.fillStyle = 'rgba(0, 0, 0, 0.06)';
    for (let y = 0; y < H; y += 3) {
      ctx.fillRect(0, y, W, 1);
    }
  }, []);

  // ── Camera lifecycle ────────────────────────────────────────────────────
  const stopCamera = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setCamState('stopped');
  }, []);

  const startCamera = useCallback(async () => {
    if (camState === 'requesting') return;
    setCamState('requesting');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 320 }, height: { ideal: 240 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCamState('active');
      rafRef.current = requestAnimationFrame(renderLoop);
    } catch (err: unknown) {
      const name = (err as Error)?.name ?? '';
      if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
        setCamState('denied');
      } else {
        setCamState('error');
      }
    }
  }, [camState, renderLoop]);

  // Auto-start on mount
  useEffect(() => {
    startCamera();
    return () => {
      // Cleanup on unmount: stop RAF + release MediaStream tracks
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(t => t.stop());
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Status label ────────────────────────────────────────────────────────
  const STATUS_LABEL: Record<CameraState, string> = {
    idle:       'INITIALISING',
    requesting: 'REQUESTING ACCESS',
    active:     'CAMERA ACTIVE',
    denied:     'PERMISSION DENIED',
    error:      'CAMERA ERROR',
    stopped:    'CAMERA STOPPED',
  };

  const isActive = camState === 'active';
  const isFailed = camState === 'denied' || camState === 'error';

  return (
    <section className="panel thermal-view-panel">
      {/* Panel title */}
      <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'space-between' }}>
        <span>⬡ Thermal Situational View</span>
        <span className="thermal-sim-badge">SIMULATED</span>
      </div>

      {/* Main canvas or fallback */}
      <div className="thermal-canvas-wrap">
        {/* Hidden video element — source for canvas rendering */}
        <video
          ref={videoRef}
          muted
          playsInline
          aria-hidden="true"
          style={{ display: 'none' }}
        />

        {isActive ? (
          <canvas
            ref={canvasRef}
            className="thermal-canvas"
            width={320}
            height={240}
            aria-label="Simulated thermal visualization from webcam"
          />
        ) : isFailed ? (
          <div className="thermal-fallback">
            <div className="thermal-fallback-icon">⊘</div>
            <div className="thermal-fallback-title">THERMAL CAMERA UNAVAILABLE</div>
            <div className="thermal-fallback-sub">
              {camState === 'denied'
                ? 'Camera permission denied by browser.'
                : 'Could not access camera device.'}
            </div>
            <div className="thermal-fallback-note">
              Using synthetic thermal pipeline data
            </div>
          </div>
        ) : (
          <div className="thermal-fallback">
            <div className="thermal-fallback-icon" style={{ opacity: .5 }}>◌</div>
            <div className="thermal-fallback-sub">{STATUS_LABEL[camState]}</div>
          </div>
        )}
      </div>

      {/* Footer bar */}
      <div className="thermal-footer">
        <span
          className="thermal-status-dot-label"
          style={{ color: isActive ? 'var(--safe)' : isFailed ? 'var(--critical)' : 'var(--caution)' }}
        >
          <span
            className="thermal-status-dot"
            style={{ background: isActive ? 'var(--safe)' : isFailed ? 'var(--critical)' : 'var(--caution)' }}
          />
          {STATUS_LABEL[camState]}
        </span>

        <span className="thermal-source-label">WEBCAM SOURCE · SIMULATED THERMAL</span>

        {isActive ? (
          <button className="thermal-ctrl-btn" onClick={stopCamera}>
            STOP
          </button>
        ) : !isFailed && camState !== 'requesting' ? (
          <button className="thermal-ctrl-btn" onClick={() => { setCamState('idle'); startCamera(); }}>
            START
          </button>
        ) : isFailed ? (
          <button className="thermal-ctrl-btn" onClick={() => { setCamState('idle'); startCamera(); }}>
            RETRY
          </button>
        ) : null}
      </div>
    </section>
  );
}
