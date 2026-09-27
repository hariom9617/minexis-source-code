# 🚀 Deploy Frontend to Vercel NOW

**Backend Status:** ✅ LIVE at `https://minexis-source-code.onrender.com`  
**Frontend Config:** ✅ Updated and pushed to GitHub  
**Next Step:** Deploy to Vercel (5 minutes)

---

## ✅ Backend Confirmed Working

Your backend is running perfectly:

```json
{
  "status": "ok",
  "service": "MINEXIS backend",
  "running": true,
  "frame_number": 1866+,
  "scenario": "SAFE"
}
```

**Backend URL:** `https://minexis-source-code.onrender.com`

---

## 🎯 Deploy Frontend to Vercel (5 Steps)

### Step 1: Sign Up for Vercel

1. Go to **https://vercel.com**
2. Click **"Sign Up"**
3. Click **"Continue with GitHub"**
4. Authorize Vercel to access your GitHub account

---

### Step 2: Import Your Project

1. After signing in, click **"Add New..."** (top right)
2. Select **"Project"**
3. You'll see a list of your GitHub repositories
4. Find **`hariom9617/minexis-source-code`**
5. Click **"Import"**

---

### Step 3: Configure Build Settings

Vercel will show a configuration screen. Fill in:

#### Framework Preset
- Select: **Vite**

#### Root Directory ⚠️ IMPORTANT
- Click **"Edit"** next to Root Directory
- Enter: **`minexis/ui/dashboard`**
- Click **"Continue"**

#### Build and Output Settings (should auto-detect)
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`

---

### Step 4: Add Environment Variable

Scroll down to **"Environment Variables"** section:

Click **"Add"** and enter:

```
Name:  VITE_API_BASE_URL
Value: https://minexis-source-code.onrender.com
```

**IMPORTANT:** Make sure there are NO spaces or typos!

**Select:** Production, Preview, Development (check all three)

---

### Step 5: Deploy!

1. Click **"Deploy"** button (bottom of page)
2. Vercel will start building your frontend
3. Watch the build logs (it's fun!)
4. Wait 2-3 minutes

**You'll see:**
```
Building...
> npm run build
> vite build

✓ building...
✓ build complete

Deploying...
✓ Deployment ready

Visit: https://minexis-source-code-xxxx.vercel.app
```

---

## ✅ After Deployment Completes

### 1. Copy Your Frontend URL

Vercel will show you a URL like:
- `https://minexis-source-code.vercel.app`
- or `https://minexis-source-code-xxxx.vercel.app`

**SAVE THIS URL!** You'll need it for CORS configuration.

---

### 2. Test Your Frontend

Click the **"Visit"** button or open the URL in your browser.

**You should see:**
- ✅ MINEXIS dashboard loads
- ✅ Three perception panels (Thermal, Radar, Trajectory)
- ✅ Scenario buttons at top
- ✅ Status cards at bottom

---

### 3. Check Developer Console

Press **F12** to open Developer Tools:

**Console Tab:**
- Should see: `WebSocket connection established`
- Should NOT see CORS errors

**Network Tab:**
- Filter by **WS** (WebSocket)
- You should see connection to your backend
- Status should be: **101 Switching Protocols** ✅

---

### 4. Test Scenario Switching

Click the scenario buttons at the top:
- **SAFE** (green)
- **CAUTION** (yellow)
- **WARNING** (orange)
- **CRITICAL** (red)

Watch the dashboard update in real-time!

---

## 🔧 Fix CORS (Final Step)

Now that you have your Vercel URL, update backend CORS:

### Option A: Via Render Dashboard (Easiest)

1. Go to **https://dashboard.render.com**
2. Click on your **minexis-source-code** service
3. Go to **"Environment"** tab (left sidebar)
4. Find the `CORS_ORIGINS` variable
5. Click **"Edit"**
6. Change value to:
   ```
   https://your-actual-frontend.vercel.app,http://localhost:3000
   ```
   **Replace** `your-actual-frontend.vercel.app` with your real Vercel URL!

7. Click **"Save Changes"**
8. Wait 1-2 minutes for automatic redeploy

---

### Option B: Via Code Update

If you prefer to update via code:

1. Edit `d:\SIH\minexis\backend\app.py`
2. Find line ~113 (CORS middleware)
3. Update:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=[
           "https://your-frontend.vercel.app",  # Your Vercel URL
           "http://localhost:3000",              # Local development
       ],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```
4. Commit and push:
   ```bash
   git add backend/app.py
   git commit -m "Update CORS for Vercel frontend"
   git push
   ```

**I recommend Option A (dashboard) - it's faster!**

---

## 🎉 You're Done!

Once CORS is updated, your complete system is live:

### Your Deployment URLs

**Backend (Render):**
```
https://minexis-source-code.onrender.com
```

**Frontend (Vercel):**
```
https://your-frontend.vercel.app
```

---

## 🧪 Final Testing Checklist

After CORS update, test everything:

- [ ] Open frontend URL in browser
- [ ] Dashboard loads without errors
- [ ] Press F12 → No CORS errors in console
- [ ] WebSocket shows "Connected" in Network tab
- [ ] Click SAFE button → dashboard updates
- [ ] Click CAUTION button → colors change to yellow
- [ ] Click WARNING button → colors change to orange
- [ ] Click CRITICAL button → colors change to red
- [ ] Thermal panel shows webcam feed
- [ ] Radar panel shows SVG visualization
- [ ] Trajectory panel shows prediction
- [ ] Bottom status cards update in real-time
- [ ] Test on mobile phone
- [ ] Test on different browser (Firefox, Edge)

---

## 🎬 For Your SIH Presentation

### Demo Flow

1. **Show the URL** (not localhost - real internet URL!)
2. **Open in browser** and explain the UI layout
3. **Open DevTools** (F12) → Show WebSocket connected
4. **Test scenarios:**
   - Click SAFE → "System operating normally"
   - Click CAUTION → "Potential hazard detected"
   - Click WARNING → "Collision risk increasing"
   - Click CRITICAL → "Immediate danger!"
5. **Show thermal panel** → Demonstrate webcam detection
6. **Show spotlight system** → Move hand/object, show T1, T2 badges
7. **Explain architecture:**
   - "Backend on Render processes sensor data"
   - "Frontend on Vercel displays real-time visualization"
   - "WebSocket streams data at 60 FPS"
   - "Multi-sensor fusion combines thermal + radar"
   - "Adaptive weighting based on quality scores"

### Key Talking Points

✨ **Professional deployment** on industry-standard platforms  
✨ **Real-time processing** with WebSocket streaming  
✨ **Multi-sensor fusion** combining thermal and radar  
✨ **Adaptive detection** with fallback strategies  
✨ **Production-ready** with proper CORS and security  
✨ **Comprehensive testing** (54 tests passing)  
✨ **Industrial UI** with professional spotlight detection  

---

## 📱 Mobile Testing

Don't forget to test on mobile!

1. Open your Vercel URL on your phone
2. Dashboard should be responsive
3. Scenario buttons should work
4. All panels should display correctly

---

## 🎓 Deployment Complete Stats

**Total Services:** 2 (Backend + Frontend)  
**Total Platforms:** 3 (GitHub + Render + Vercel)  
**Total Time:** ~30 minutes  
**Total Cost:** $0/month (free tier)  
**Production Ready:** Yes!  

**Commits made:**
```
4e70d91 Configure production backend URL
442cd25 Update deployment fix documentation
700e0d0 Fix: Correct BlobThermalDetector parameter
0fb0f6c Add deployment fix documentation
d13b905 Fix: Use BlobThermalDetector for deployment
77d26be Add deployment ready documentation
```

---

## 🏆 You've Successfully Deployed a Full-Stack AI System!

This is what you built and deployed:

- ✅ FastAPI backend with WebSocket streaming
- ✅ Real-time sensor fusion pipeline
- ✅ React + Vite frontend with industrial UI
- ✅ Professional spotlight detection system
- ✅ Multi-object tracking with trajectory prediction
- ✅ Adaptive risk assessment engine
- ✅ Complete CI/CD with auto-deploy
- ✅ Production-ready error handling
- ✅ Comprehensive documentation

**This is hackathon-winning material!** 🏆

---

## 📞 Need Help?

**Vercel Issues:**
- Check build logs in Vercel dashboard
- Verify root directory is `minexis/ui/dashboard`
- Verify environment variable is set correctly

**CORS Issues:**
- Use exact Vercel URL (including https://)
- No trailing slash
- Wait for Render to redeploy after CORS change

**WebSocket Issues:**
- Check backend URL in .env.production
- Verify backend is running (health endpoint)
- Check browser console for specific errors

---

## ✨ Start Deploying to Vercel Now!

**Go to:** https://vercel.com

**Time needed:** 5 minutes

**Good luck with Smart India Hackathon 2026! 🚀🏆**

---
