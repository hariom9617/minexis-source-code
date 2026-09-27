/**
 * useWarningSound — Web Audio API-based warning buzzer.
 *
 * Plays synthesized warning tones when risk state is WARNING or CRITICAL.
 * Handles browser autoplay restrictions by requiring user interaction first.
 *
 * WARNING state: moderate beep pattern (once per ~1.2s)
 * CRITICAL state: urgent rapid beeps (twice per second)
 *
 * Usage:
 *   const { soundEnabled, toggleSound, initAudio } = useWarningSound(riskState);
 *   // User must click a button to call initAudio() first due to browser policy
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { RiskState } from '../types';

// Audio parameters
const WARNING_BEEP_INTERVAL_MS  = 1200;  // moderate pace
const CRITICAL_BEEP_INTERVAL_MS = 500;   // urgent rapid pace

const BEEP_FREQUENCY_HZ = 800;           // tone frequency
const BEEP_DURATION_MS  = 120;           // beep length

export interface WarningSound {
  soundEnabled: boolean;
  toggleSound: () => void;
  initAudio: () => void;
}

export function useWarningSound(riskState: RiskState): WarningSound {
  const [soundEnabled, setSoundEnabled] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const beepIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastRiskRef = useRef<RiskState>('safe');

  // Initialize AudioContext (must be called from user interaction)
  const initAudio = useCallback(() => {
    if (audioContextRef.current) return; // already initialized
    try {
      audioContextRef.current = new AudioContext();
      setSoundEnabled(true);
    } catch (err) {
      console.warn('Failed to initialize AudioContext:', err);
    }
  }, []);

  // Play a single beep
  const playBeep = useCallback(() => {
    const ctx = audioContextRef.current;
    if (!ctx || !soundEnabled) return;

    try {
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();

      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);

      oscillator.frequency.value = BEEP_FREQUENCY_HZ;
      oscillator.type = 'sine';

      // Envelope: quick attack, sustain, quick release
      const now = ctx.currentTime;
      gainNode.gain.setValueAtTime(0, now);
      gainNode.gain.linearRampToValueAtTime(0.15, now + 0.01);  // attack
      gainNode.gain.setValueAtTime(0.15, now + BEEP_DURATION_MS / 1000 - 0.02);
      gainNode.gain.linearRampToValueAtTime(0, now + BEEP_DURATION_MS / 1000);  // release

      oscillator.start(now);
      oscillator.stop(now + BEEP_DURATION_MS / 1000);
    } catch (err) {
      console.warn('Failed to play beep:', err);
    }
  }, [soundEnabled]);

  // Toggle sound on/off
  const toggleSound = useCallback(() => {
    if (!audioContextRef.current) {
      // First time: initialize
      initAudio();
    } else {
      setSoundEnabled(prev => !prev);
    }
  }, [initAudio]);

  // Effect: manage beep interval based on risk state
  useEffect(() => {
    // Clear any existing interval
    if (beepIntervalRef.current) {
      clearInterval(beepIntervalRef.current);
      beepIntervalRef.current = null;
    }

    // Only play sounds if enabled and risk is WARNING or CRITICAL
    if (!soundEnabled || (riskState !== 'warning' && riskState !== 'critical')) {
      lastRiskRef.current = riskState;
      return;
    }

    // Determine beep interval
    const interval = riskState === 'critical' 
      ? CRITICAL_BEEP_INTERVAL_MS 
      : WARNING_BEEP_INTERVAL_MS;

    // Play immediate beep when entering WARNING/CRITICAL (if transitioning from lower state)
    const prevRiskOrder = lastRiskRef.current === 'safe' ? 0 : lastRiskRef.current === 'caution' ? 1 : 2;
    const currRiskOrder = riskState === 'warning' ? 2 : 3;
    if (currRiskOrder > prevRiskOrder) {
      playBeep();
    }

    // Start repeating beeps
    beepIntervalRef.current = setInterval(() => {
      playBeep();
    }, interval);

    lastRiskRef.current = riskState;

    return () => {
      if (beepIntervalRef.current) {
        clearInterval(beepIntervalRef.current);
        beepIntervalRef.current = null;
      }
    };
  }, [riskState, soundEnabled, playBeep]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (beepIntervalRef.current) {
        clearInterval(beepIntervalRef.current);
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
    };
  }, []);

  return {
    soundEnabled,
    toggleSound,
    initAudio,
  };
}
