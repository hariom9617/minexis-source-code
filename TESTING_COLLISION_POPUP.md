# Testing Guide: Collision Risk Popup

## Quick Start

### 1. Start Backend
```bash
cd d:\SIH\minexis
python main.py
```

Expected output:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 2. Open Dashboard
Navigate to: `http://localhost:8000`

### 3. Enable Sound (Optional)
Click the **"🔇 SOUND OFF"** button in the header to activate audio warnings.

### 4. Start COLLISION_DEMO
Click the **"COLLISION DEMO"** button in the header simulation controls.

### 5. Wait for Popup
The collision risk popup should appear after approximately **6 seconds** when the object reaches 40 meters.

---

## What You Should See

### Timeline

| Time | Distance | Risk State | Expected Behavior |
|------|----------|------------|-------------------|
| 0s   | 100.0m   | SAFE       | No popup, green status |
| 2s   | ~80.0m   | CAUTION    | Risk badge turns orange, no popup |
| 4s   | ~60.0m   | WARNING    | Risk badge pulses orange, audio beeps |
| 6s   | ~40.0m   | WARNING    | **POPUP APPEARS** 🔴 |
| 7s   | ~30.0m   | CRITICAL   | Popup shows, risk critical, faster beeps |
| 8s   | ~20.0m   | CRITICAL   | Distance decreasing in popup |
| 9s   | ~10.0m   | CRITICAL   | Very close, popup shows low distance |
| 10s  | ~2.0m    | CRITICAL   | Object resets to 100m, popup dismisses |

---

## Popup Appearance Checklist

### Visual Elements
- [ ] Full-screen dark red overlay covers entire dashboard
- [ ] Central popup card with red border (3px)
- [ ] Large pulsing warning icon (⬟) at top
- [ ] "COLLISION RISK" title in large red text
- [ ] "Object within critical proximity" subtitle
- [ ] Track card(s) showing object details
- [ ] "⚠ TAKE IMMEDIATE ACTION ⚠" message at bottom

### Animations
- [ ] Popup card pulses (scale + glow) every 0.8 seconds
- [ ] Warning icon rotates 180° on each pulse
- [ ] Background overlay opacity oscillates
- [ ] All animations are smooth and synchronized

### Track Card Content
- [ ] Track ID displayed (e.g., "TRACK #1")
- [ ] Object class shown (e.g., "Unknown", "Person", "Vehicle")
- [ ] Distance value in meters (e.g., "35.2 m")
- [ ] TTC value if available (e.g., "3.5 s")
- [ ] Distance decreases in real-time

### Colors
- [ ] Dark red background gradient
- [ ] Bright red (#ef4444) borders and text
- [ ] Text has glow/shadow effects
- [ ] Track cards have subtle red tint

---

## Test Cases

### Test 1: Basic Trigger
**Steps:**
1. Start backend and open dashboard
2. Click "COLLISION DEMO"
3. Wait 6 seconds

**Expected:**
- Popup appears when object reaches 40m
- Shows one track card
- Distance value ~40.0m initially

**Pass/Fail:** _____

---

### Test 2: Distance Updates
**Steps:**
1. Trigger popup as above
2. Observe distance value in track card
3. Watch for 2-3 seconds

**Expected:**
- Distance value decreases continuously
- Updates smooth (not jumpy)
- Shows one decimal place precision

**Pass/Fail:** _____

---

### Test 3: TTC Display
**Steps:**
1. Trigger popup as above
2. Check if TTC row is visible
3. Observe TTC value

**Expected:**
- TTC row appears (if risk assessment includes it)
- Shows time in seconds with one decimal
- TTC value decreases as object approaches

**Pass/Fail:** _____

---

### Test 4: Popup Dismissal
**Steps:**
1. Wait for object to reset (at ~2m)
2. Observe popup behavior

**Expected:**
- Popup dismisses when object resets to 100m
- Dashboard returns to normal view
- No visual glitches

**Pass/Fail:** _____

---

### Test 5: Multiple Cycles
**Steps:**
1. Let scenario run for 3-4 complete cycles
2. Observe popup behavior each time

**Expected:**
- Popup appears consistently at 40m mark
- Dismisses consistently when distance > 40m
- No memory leaks or performance degradation
- Animations remain smooth

**Pass/Fail:** _____

---

### Test 6: Risk State Coordination
**Steps:**
1. Observe risk badge in top-right
2. Compare with popup timing
3. Check audio warnings (if enabled)

**Expected:**
- Risk badge state independent of popup
- Popup can appear even in WARNING state
- Audio warnings continue during popup
- All systems work together

**Pass/Fail:** _____

---

### Test 7: Visual Hierarchy
**Steps:**
1. Trigger popup
2. Try to interact with dashboard behind popup
3. Observe z-index layering

**Expected:**
- Popup completely blocks dashboard interaction
- No clicks pass through to background
- Popup is highest layer (z-index: 1000)
- Background slightly visible through overlay

**Pass/Fail:** _____

---

### Test 8: Responsive Layout
**Steps:**
1. Trigger popup
2. Resize browser window
3. Test at different viewport sizes

**Expected:**
- Popup remains centered
- Content scales appropriately
- Max width 500px maintained
- 90% width at smaller screens
- No overflow or clipping

**Pass/Fail:** _____

---

## Troubleshooting

### Popup Doesn't Appear

**Possible Causes:**
1. Object not reaching 40m threshold
2. Frontend not updated
3. Distance calculation error

**Solutions:**
```bash
# Rebuild frontend
cd d:\SIH\minexis\ui\dashboard
npm run build

# Restart backend
cd d:\SIH\minexis
python main.py

# Clear browser cache
Ctrl + Shift + R (hard refresh)
```

---

### Animations Not Working

**Possible Causes:**
1. Browser doesn't support CSS animations
2. CSS not loaded properly
3. Browser performance settings

**Solutions:**
- Check browser console for errors
- Verify CSS file loaded (check Network tab)
- Test in different browser (Chrome/Edge recommended)
- Disable browser battery saving mode

---

### Wrong Distance Values

**Possible Causes:**
1. Position calculation error
2. Coordinate system mismatch
3. Pipeline data issue

**Solutions:**
- Check browser console for track data
- Verify `position_xy` values make sense
- Confirm pipeline is sending valid data
- Check backend logs for errors

---

### Popup Stays Visible

**Possible Causes:**
1. Object stuck in tracking
2. Distance not updating
3. Conditional logic error

**Solutions:**
- Stop and restart COLLISION_DEMO scenario
- Check if tracks array is clearing
- Verify WebSocket connection active
- Refresh browser page

---

## Browser Console Inspection

### Useful Console Commands

**Check current tracks:**
```javascript
// View all active tracks
window.currentTracks = [];
// (Set breakpoint in App.tsx to capture)
```

**Monitor distance:**
```javascript
// Add this to App.tsx temporarily for debugging
console.log('Proximity check:', {
  dangerousProximity,
  tracks: data?.tracks.map(t => ({
    id: t.track_id,
    distance: Math.hypot(t.position_xy[0], t.position_xy[1])
  }))
});
```

**Check popup render:**
```javascript
// Verify popup is in DOM
document.querySelector('.collision-popup-overlay');
// Should return element when visible, null otherwise
```

---

## Performance Metrics

### Expected Performance
- **Frame rate**: 60 FPS (smooth animations)
- **CPU usage**: <5% increase during popup
- **Memory**: No leaks (<50MB growth over 10 minutes)
- **Render time**: <16ms per frame

### Monitoring
1. Open DevTools → Performance tab
2. Start recording
3. Trigger popup
4. Let run for 30 seconds
5. Stop recording
6. Analyze:
   - Look for long tasks (>50ms)
   - Check for layout thrashing
   - Verify GPU acceleration active

---

## Success Criteria

### Minimum Requirements
- ✅ Popup appears at 40m threshold
- ✅ Distance value displays and updates
- ✅ Popup dismisses when object leaves zone
- ✅ No errors in console
- ✅ Animations are smooth

### Full Feature Validation
- ✅ All visual elements present
- ✅ All animations working
- ✅ Track card shows correct data
- ✅ TTC displayed when available
- ✅ Works across multiple cycles
- ✅ Coordinated with risk system
- ✅ Proper z-index layering
- ✅ Responsive to window size
- ✅ No performance degradation
- ✅ No memory leaks

---

## Known Limitations

1. **No Manual Dismissal**
   - Popup automatically dismisses at >40m
   - No close button implemented
   - Operator cannot acknowledge/dismiss

2. **Fixed Threshold**
   - Hardcoded 40m threshold
   - Not configurable via UI
   - Requires code change to adjust

3. **No Direction Info**
   - Shows distance but not direction
   - No arrow or compass indicator
   - Could add in future

4. **Passive Display**
   - No interactive elements
   - No action buttons
   - Information only

---

## Reporting Issues

If you encounter problems:

1. **Take Screenshot** of popup and console
2. **Note Timestamp** when issue occurred
3. **Copy Console Errors** (if any)
4. **Document Steps** to reproduce
5. **Check Files:**
   - `d:\SIH\minexis\ui\dashboard\src\App.tsx`
   - `d:\SIH\minexis\ui\dashboard\src\styles\dashboard.css`

---

## Sign-Off

| Test Area | Status | Tester | Date |
|-----------|--------|--------|------|
| Visual Appearance | ⬜ Pass ⬜ Fail | ______ | ____ |
| Animations | ⬜ Pass ⬜ Fail | ______ | ____ |
| Distance Updates | ⬜ Pass ⬜ Fail | ______ | ____ |
| TTC Display | ⬜ Pass ⬜ Fail | ______ | ____ |
| Dismissal Logic | ⬜ Pass ⬜ Fail | ______ | ____ |
| Multi-Cycle | ⬜ Pass ⬜ Fail | ______ | ____ |
| Performance | ⬜ Pass ⬜ Fail | ______ | ____ |
| Responsive | ⬜ Pass ⬜ Fail | ______ | ____ |

**Overall Status:** ⬜ PASS ⬜ FAIL

**Comments:**
_______________________________________________________________
_______________________________________________________________
_______________________________________________________________

---

**Testing Guide Version:** 1.0  
**Last Updated:** 2026-09-14  
**Feature Status:** Complete ✅
