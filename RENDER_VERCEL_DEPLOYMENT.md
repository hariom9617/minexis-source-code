# MINEXIS Deployment Guide
## Render (Backend) + Vercel (Frontend)

**Repository:** https://github.com/hariom9617/minexis-source-code.git

---

## 🎯 Quick Deployment Overview

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Vercel)          Backend (Render)            │
│  ┌──────────────┐          ┌──────────────────┐        │
│  │ React + Vite │◄────────►│ FastAPI + Python │        │
│  │ Dashboard UI │  HTTP/WS │ Pipeline Engine  │        │
│  └──────────────┘          └──────────────────┘        │
│  vercel.app                 onrender.com               │
└─────────────────────────────────────────────────────────┘
```

---

## Part 1: Deploy Backend to Render 🚀

### Step 1: Push Code to GitHub

```bash
cd d:\SIH\minexis
git init
git add .
git commit -m "Initial commit: MINEXIS complete system"
git branch -M main
git remote add origin https://github.com/hariom9617/minexis-source-code.git
git push -u origin main
```

### Step 2: Sign Up for Render

1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Sign up with your **GitHub account**
4. Authorize Render to access your GitHub repositories

### Step 3: Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Click **"Connect a repository"**
3. Find and select: **`hariom9617/minexis-source-code`**
4. Click **"Connect"**

### Step 4: Configure Web Service

Fill in the following settings:

**Basic Settings:**
- **Name:** `minexis-backend` (or your preferred name)
- **Region:** Choose closest to your location
- **Branch:** `main`
- **Root Directory:** `minexis`
- **Runtime:** `Python 3`

**Build & Deploy:**
- **Build Command:**
  ```bash
  pip install -r requirements.txt
  ```

- **Start Command:**
  ```bash
  uvicorn backend.app:app --host 0.0.0.0 --port $PORT
  ```

**Instance Type:**
- **Free** (for demo/hackathon)
- Or **Starter** ($7/month for better performance)

### Step 5: Add Environment Variables

Click **"Advanced"** → **"Add Environment Variable"**

Add the following:

```
PYTHON_VERSION=3.11
PORT=10000
CORS_ORIGINS=*
LOG_LEVEL=INFO
```

### Step 6: Deploy

1. Click **"Create Web Service"**
2. Wait 5-10 minutes for deployment
3. Watch the logs for any errors
4. Once deployed, copy your backend URL:
   - Example: `https://minexis-backend.onrender.com`

### Step 7: Test Backend

Open in browser or use curl:
```bash
# Test health endpoint
curl https://your-app-name.onrender.com/health

# Test scenarios endpoint
curl https://your-app-name.onrender.com/api/scenarios
```

---

## Part 2: Deploy Frontend to Vercel 🌐

### Step 1: Update Frontend Configuration

Create `.env.production` file:

```bash
cd d:\SIH\minexis\ui\dashboard
```

Create file named `.env.production` with:
```env
VITE_API_BASE_URL=https://your-app-name.onrender.com
```

**Replace** `your-app-name.onrender.com` with your actual Render backend URL!

### Step 2: Commit Frontend Changes

```bash
cd d:\SIH\minexis
git add ui/dashboard/.env.production
git commit -m "Add production environment config"
git push origin main
```

### Step 3: Sign Up for Vercel

1. Go to **https://vercel.com**
2. Click **"Sign Up"**
3. Sign up with your **GitHub account**
4. Authorize Vercel to access your repositories

### Step 4: Import Project

1. Click **"Add New..."** → **"Project"**
2. Find and select: **`hariom9617/minexis-source-code`**
3. Click **"Import"**

### Step 5: Configure Project

**Framework Preset:**
- Select: **Vite**

**Root Directory:**
- Click **"Edit"**
- Enter: `minexis/ui/dashboard`
- Click **"Continue"**

**Build Settings:**
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`

### Step 6: Add Environment Variables

Click **"Environment Variables"**

Add:
```
Name: VITE_API_BASE_URL
Value: https://your-app-name.onrender.com
```

**Important:** Use your actual Render backend URL!

### Step 7: Deploy

1. Click **"Deploy"**
2. Wait 2-5 minutes for build and deployment
3. Once completed, click **"Visit"** to see your dashboard
4. Copy your frontend URL:
   - Example: `https://minexis-dashboard.vercel.app`

### Step 8: Update Backend CORS

Go back to **Render Dashboard**:

1. Open your backend service
2. Go to **"Environment"**
3. Find `CORS_ORIGINS` variable
4. Update value to:
   ```
   https://your-frontend.vercel.app,http://localhost:3000
   ```
5. Click **"Save Changes"**
6. Service will automatically redeploy

---

## Part 3: Final Configuration & Testing 🧪

### Update CORS in Backend Code

Edit `d:\SIH\minexis\backend\app.py`:

Find the CORS middleware section and update:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-frontend.vercel.app",  # Your Vercel URL
        "http://localhost:3000",              # Local development
        "*"                                    # Allow all (for testing only)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Commit and push:
```bash
git add backend/app.py
git commit -m "Update CORS for production"
git push origin main
```

Render will automatically redeploy!

### Test Complete System

1. **Open Frontend:** `https://your-frontend.vercel.app`

2. **Check Console:**
   - Press `F12` to open Developer Tools
   - Go to **Console** tab
   - Look for any errors

3. **Check WebSocket:**
   - Go to **Network** tab
   - Filter by **WS** (WebSocket)
   - Should see connection to backend
   - Status should be **101 Switching Protocols**

4. **Test Features:**
   - Click scenario buttons (SAFE, CAUTION, WARNING, CRITICAL)
   - Watch thermal perception panel (should see webcam)
   - Check radar perception panel (should see SVG)
   - Verify trajectory panel updates
   - Check bottom cards show data

---

## 🎯 Deployment Checklist

### Backend (Render) ✅
- [ ] Code pushed to GitHub
- [ ] Render service created and connected
- [ ] Build command configured
- [ ] Start command configured
- [ ] Environment variables added
- [ ] Service deployed successfully
- [ ] Health endpoint responding
- [ ] WebSocket endpoint accessible
- [ ] CORS configured for frontend domain

### Frontend (Vercel) ✅
- [ ] `.env.production` created with backend URL
- [ ] Changes pushed to GitHub
- [ ] Vercel project imported
- [ ] Root directory set correctly
- [ ] Build command configured
- [ ] Environment variables added
- [ ] Site deployed successfully
- [ ] Dashboard loads without errors
- [ ] WebSocket connects to backend
- [ ] Real-time data flows correctly

---

## 📋 Your Deployment URLs

Fill in after deployment:

**Backend (Render):**
```
https://_____________________.onrender.com
```

**Frontend (Vercel):**
```
https://_____________________.vercel.app
```

---

## 🔧 Troubleshooting Guide

### Issue 1: Backend "Application Error" on Render

**Symptoms:** Render shows "Application failed to respond"

**Solutions:**
1. Check Render logs: Dashboard → Service → Logs
2. Verify `requirements.txt` has all dependencies
3. Ensure start command is: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Check Python version: Should be 3.11
5. Verify root directory is set to `minexis`

### Issue 2: Frontend Build Failed on Vercel

**Symptoms:** Vercel build fails with npm errors

**Solutions:**
1. Check Vercel build logs
2. Verify root directory: `minexis/ui/dashboard`
3. Run `npm run build` locally to test
4. Check Node.js version (should be 18+)
5. Delete `node_modules` and `package-lock.json`, reinstall

### Issue 3: CORS Error in Browser

**Symptoms:** Console shows "CORS policy blocked"

**Solutions:**
1. Update `CORS_ORIGINS` in Render environment variables
2. Include your Vercel URL: `https://your-app.vercel.app`
3. Restart Render service
4. Clear browser cache
5. Hard refresh: `Ctrl + Shift + R`

### Issue 4: WebSocket Connection Failed

**Symptoms:** "WebSocket connection failed" in console

**Solutions:**
1. Check backend URL uses `https://` (should auto-convert to `wss://`)
2. Verify `/ws/live` endpoint exists in backend
3. Check Render logs for WebSocket errors
4. Ensure WebSocket is enabled on Render (it is by default)
5. Test WebSocket in browser console:
   ```javascript
   const ws = new WebSocket('wss://your-backend.onrender.com/ws/live');
   ws.onopen = () => console.log('Connected!');
   ```

### Issue 5: Render Free Tier "Spinning Down"

**Symptoms:** First load takes 30+ seconds

**Why:** Render free tier spins down after 15 minutes of inactivity

**Solutions:**
1. Use UptimeRobot to ping every 14 minutes (keeps it alive)
2. Upgrade to Starter plan ($7/month, no spin down)
3. Accept cold starts for demo (mention in presentation)
4. Use Railway instead (free tier doesn't spin down)

---

## 💰 Cost Breakdown

### Free Tier (Hackathon/Demo)
- **Render:** Free (with cold starts)
- **Vercel:** Free (unlimited hobby projects)
- **Total:** $0/month

**Limitations:**
- Backend spins down after 15 min inactivity
- 750 hours/month on Render free tier
- First load: 30s cold start

### Paid Tier (Production)
- **Render Starter:** $7/month (no cold starts)
- **Vercel:** Free (or $20/month Pro for teams)
- **Total:** $7-27/month

---

## 🚀 Auto-Deploy Setup

Both Render and Vercel support automatic deployments!

**How it works:**
1. Push code to GitHub `main` branch
2. Render automatically rebuilds backend
3. Vercel automatically rebuilds frontend
4. Changes live in 2-5 minutes

**To deploy updates:**
```bash
cd d:\SIH\minexis
# Make your changes
git add .
git commit -m "Your update message"
git push origin main
```

Both services will automatically detect the push and redeploy!

---

## 📱 Custom Domain Setup (Optional)

### For Frontend (Vercel)

1. Go to Vercel Dashboard → Your Project
2. Click **"Settings"** → **"Domains"**
3. Enter your domain: `minexis.yourdomain.com`
4. Follow DNS instructions (add CNAME record)
5. SSL certificate auto-generated

### For Backend (Render)

1. Go to Render Dashboard → Your Service
2. Click **"Settings"** → **"Custom Domain"**
3. Enter domain: `api.minexis.yourdomain.com`
4. Add CNAME record to DNS
5. SSL certificate auto-generated

---

## 📊 Monitoring & Logs

### Render Logs (Backend)
- **Real-time:** Dashboard → Service → Logs
- **Events:** Dashboard → Service → Events
- **Metrics:** CPU, Memory, Network usage

### Vercel Analytics (Frontend)
- **Performance:** Dashboard → Analytics
- **Deployment:** Dashboard → Deployments
- **Logs:** Click on any deployment → View Logs

### Recommended Monitoring Tools
- **UptimeRobot** (uptimerobot.com) - Free uptime monitoring
- **Sentry** (sentry.io) - Error tracking
- **Google Analytics** - User tracking

---

## 🎬 Pre-Presentation Checklist

**24 Hours Before:**
- [ ] Test complete user flow
- [ ] Check all scenarios work
- [ ] Verify WebSocket connection stable
- [ ] Test on different browsers (Chrome, Firefox, Edge)
- [ ] Test on mobile device
- [ ] Take screenshots/video for backup

**1 Hour Before:**
- [ ] Visit site to wake up backend (free tier)
- [ ] Check browser console for errors
- [ ] Verify all three perception panels load
- [ ] Test scenario switching
- [ ] Keep local version ready as backup

**During Presentation:**
- [ ] Have URLs bookmarked
- [ ] Keep Developer Console open (to show real-time WebSocket)
- [ ] Demonstrate spotlight detection with hand/object
- [ ] Show multiple object tracking
- [ ] Explain trajectory prediction

---

## 📞 Quick Support Links

**Render:**
- Documentation: https://render.com/docs
- Status Page: https://status.render.com
- Discord: https://discord.gg/render

**Vercel:**
- Documentation: https://vercel.com/docs
- Help: https://vercel.com/help
- Discord: https://vercel.com/discord

---

## ✨ Success!

Your MINEXIS system is now live on the internet! 🎉

**Share your demo:**
- Frontend: `https://your-app.vercel.app`
- Backend API: `https://your-app.onrender.com`

**For Smart India Hackathon presentation:**
1. Show live demo URL
2. Demonstrate real-time detection
3. Explain the spotlight system
4. Show trajectory prediction
5. Mention deployment on professional platforms

**Good luck with your hackathon! 🏆**

---

