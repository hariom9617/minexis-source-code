# Collision Risk Popup Design Specification

## Visual Design Overview

The collision risk popup provides an unmissable full-screen warning when any object comes within 40 meters of the vehicle.

## Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                    [Dark Red Overlay]                       │
│                     (with blur effect)                       │
│                                                              │
│              ┌────────────────────────────┐                 │
│              │    ⬟                       │                 │
│              │   [Pulsing Icon]           │                 │
│              │                            │                 │
│              │    COLLISION RISK          │                 │
│              │  [Large Bold Title]        │                 │
│              │                            │                 │
│              │  Object within critical    │                 │
│              │      proximity             │                 │
│              │                            │                 │
│              │  ┌──────────────────────┐  │                 │
│              │  │ TRACK #1    Person  │  │                 │
│              │  │ Distance:    35.2 m │  │                 │
│              │  │ TTC:         3.5 s  │  │                 │
│              │  └──────────────────────┘  │                 │
│              │                            │                 │
│              │  ┌──────────────────────┐  │                 │
│              │  │ TRACK #2   Vehicle  │  │                 │
│              │  │ Distance:    28.7 m │  │                 │
│              │  │ TTC:         2.9 s  │  │                 │
│              │  └──────────────────────┘  │                 │
│              │                            │                 │
│              │ ⚠ TAKE IMMEDIATE ACTION ⚠ │                 │
│              │   [Pulsing Warning Box]   │                 │
│              └────────────────────────────┘                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Color Scheme

### Background
- **Overlay**: `rgba(20, 5, 5, 0.95)` — Deep red-black
- **Popup**: Dark gradient from `rgba(15, 5, 5, 0.98)` to `rgba(25, 8, 8, 0.98)`
- **Border**: 3px solid `#ef4444` (critical red)

### Typography
- **Title**: `#ef4444` with glow shadow
- **Subtitle**: `rgba(239, 68, 68, 0.9)`
- **Track Cards**: Dark red background with lighter red borders
- **Values**: Bright red `#ef4444` for emphasis

## Animation System

### 1. Collision Pulse (0.8s cycle)
**Applied to:** Main popup card and action text
```css
0%, 100% → scale(1.0) with medium glow
50%      → scale(1.02) with strong glow
```

### 2. Icon Pulse (0.8s cycle)
**Applied to:** Warning icon (⬟)
```css
0%, 100% → scale(1.0), rotate(0°), opacity(1.0)
50%      → scale(1.15), rotate(180°), opacity(0.8)
```

### 3. Overlay Glow (1.5s cycle)
**Applied to:** Background overlay
```css
0%, 100% → opacity(0.4)
50%      → opacity(0.8)
```

## Component Breakdown

### 1. Icon Wrapper
- Size: 100x100px
- Radial gradient background
- Icon font size: 72px
- Text shadow with red glow

### 2. Title Section
- Font: Monospace (JetBrains Mono)
- Size: 36px
- Weight: 900 (ultra-bold)
- Letter spacing: 6px
- Text shadow: Double layer glow

### 3. Track Cards
- Background: `rgba(239, 68, 68, 0.08)`
- Border: 2px solid `rgba(239, 68, 68, 0.4)`
- Border radius: 10px
- Padding: 14px 16px

**Each card contains:**
- **Header**: Track ID + Object class badge
- **Info rows**: Distance and TTC (if available)
- **Styling**: Dark background with red accent borders

### 4. Action Text
- Font size: 16px
- Weight: 900
- Padding: 12px 24px
- Border: 2px solid critical red
- Background: `rgba(239, 68, 68, 0.1)`
- Pulsing animation at 0.6s

## Trigger Logic

### Activation Condition
```typescript
dangerousProximity = tracks.some(track => 
  Math.hypot(track.position_xy[0], track.position_xy[1]) <= 40
)
```

### Display Logic
- Renders when `dangerousProximity === true`
- Shows ALL tracks within 40m simultaneously
- Each track displayed in individual card
- Updates distance in real-time

## Z-Index Hierarchy

```
Status bar (footer)     : 10
Disconnected overlay    : 999
Collision popup         : 1000 (highest)
```

## Responsive Behavior

- **Max width**: 500px
- **Width**: 90% of viewport
- **Centering**: Flexbox center alignment
- **Overflow**: Scroll if content exceeds viewport

## Testing Scenarios

### Test 1: Single Object at 40m
- **Expected**: Popup appears with one track card
- **Duration**: Remains visible while distance ≤ 40m

### Test 2: Multiple Objects
- **Expected**: Multiple track cards stacked vertically
- **Max tracks**: No limit (scrollable if many)

### Test 3: Object Approaching
- **Expected**: Distance values decrease in real-time
- **TTC display**: Shows if available from risk assessment

### Test 4: Object Leaving Zone
- **Expected**: Popup dismisses when distance > 40m
- **Transition**: Instant (no fade animation)

### Test 5: COLLISION_DEMO Scenario
- **Time to trigger**: ~6 seconds (100m → 40m at 10 m/s)
- **Expected behavior**: 
  - Popup appears at t=6s
  - Distance decreases: 40m → 30m → 20m → 10m
  - TTC shown if calculated
  - Popup remains until object stops or resets

## Accessibility

### Visual Attention
- ✅ Full-screen modal (impossible to miss)
- ✅ High contrast red/black color scheme
- ✅ Large text sizes (36px title, 16px values)
- ✅ Multiple animation types (scale, rotate, glow)

### Readability
- ✅ Monospace font for numeric values
- ✅ Clear label/value separation
- ✅ Adequate spacing between elements
- ✅ Text shadows for legibility

### Performance
- ✅ Pure CSS animations (no JavaScript intervals)
- ✅ GPU-accelerated transforms
- ✅ Efficient conditional rendering
- ✅ No impact on pipeline performance

## Browser Compatibility

### Required Features
- CSS Grid/Flexbox (✅ All modern browsers)
- CSS animations (✅ All modern browsers)
- Backdrop filter (✅ Chrome/Edge/Safari, Firefox 103+)
- CSS gradients (✅ All modern browsers)

### Fallback Behavior
- If backdrop-filter unsupported: solid background still visible
- If animations disabled: static popup still renders
- If CSS3 unsupported: basic layout preserved

## Future Enhancement Ideas

1. **Configurable Threshold**
   - Allow operators to set custom distance (20m, 30m, 50m)
   - Store in user preferences

2. **Audio Integration**
   - Urgent siren sound when popup appears
   - Different tones for different distances

3. **Acknowledgment Required**
   - Add "I UNDERSTAND" button
   - Log operator acknowledgment timestamp
   - Prevent dismissal until acknowledged

4. **Direction Indicator**
   - Arrow pointing to threat direction
   - Color-coded by risk severity

5. **Countdown Timer**
   - Show seconds until collision
   - Extrapolate from closing speed

6. **Recommended Action**
   - "STOP VEHICLE"
   - "REVERSE IMMEDIATELY"
   - Based on distance and TTC

7. **Multiple Severity Levels**
   - 40m: Yellow warning
   - 20m: Orange alert
   - 10m: Red critical (current style)

8. **Haptic Feedback**
   - Vibration on mobile devices
   - Escalating intensity as distance decreases

## Implementation Status

✅ **Complete**
- Full-screen overlay
- Dramatic red theme
- Pulsing animations
- Track card display
- Distance calculation
- TTC integration
- Real-time updates

⏳ **Not Implemented**
- Dismiss button
- Acknowledgment logging
- Direction arrows
- Audio integration (separate feature)
- Configurable thresholds

## Files

### Implementation
- `ui/dashboard/src/App.tsx` — Popup JSX and logic
- `ui/dashboard/src/styles/dashboard.css` — All styling and animations

### Documentation
- `COLLISION_DEMO_IMPLEMENTATION_REPORT.md` — Full feature report
- `COLLISION_POPUP_DESIGN.md` — This document

---

**Design Status: Complete** ✅  
**Implementation Status: Complete** ✅  
**Testing Status: Ready** ✅
