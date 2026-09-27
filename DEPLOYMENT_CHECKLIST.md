# MINEXIS Deployment Checklist

**Repository:** https://github.com/hariom9617/minexis-source-code.git  
**Deployment Strategy:** Render (Backend) + Vercel (Frontend)

---

## ✅ Step 1: Push Code to GitHub

**Status:** Ready to push

Execute the following command to push your code:

```bash
cd d:\SIH\minexis
git push -u origin main
```

**What this does:**
- Uploads all 81 files to your GitHub repository
- Sets up the `main` branch as the default
- Enables Render and Vercel to access your code

**If you encounter authentication issues:**
1. Generate a Personal Access Token (PAT) on GitHub:
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: `repo` (full control)
   - Copy the token
2. When prompted for password, paste the token instead

---

## ✅ Step 2: Deploy Backend to Render

### 2.1 Sign Up & Connect GitHub

1. Go to **https://render.com**
2. Click **"Get Started for Free"**
3. Sign up with your **GitHub account**
4. Authorize Render to access your repositories

### 2.2 Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Find and select: **`hariom9617/minexis-source-code`**
3. Click **"Connect"**

### 2.3 Configure Service

**Fill in these exact settings:**

| Setting | Value |
|---------|-------|
| **Name** | `minexis-backend` (or your choice) |
| **Region** | Choose closest to you |
| **Branch** | `main` |
| **Root Directory** | `minexis` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn backend.app:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | **Free** (or Starter $7/mo) |

### 2.4 Add Environment Variables

Click **"Advanced"** → **"Add Environment Variable"**

Add these:

```
PYTHON_VERSION=3.11
PORT=10000
CORS_ORIGINS=*
LOG_LEVEL=INFO
```

### 2.5 Deploy

1. Click **"Create Web Service"**
2. Wait 5-10 minutes (watch the logs)
3. Once deployed, **copy your backend URL**:
   - Format: `https://minexis-backend-xxxx.onrender.com`
   - **SAVE THIS URL** — you'll need it for the frontend!

### 2.6 Test Backend

Open in browser:
```
https://your-backend-url.onrender.com/health
```

Should return:
```json
{"status":"ok","service":"MINEXIS backend"}
```

---

## ✅ Step 3: Update Frontend Configuration

**IMPORTANT:** Before deploying frontend, update the backend URL!

1. Open `d:\SIH\minexis\ui\dashboard\.env.production`
2. Replace `YOUR-APP-NAME` with your actual Render URL:
   ```env
   VITE_API_BASE_URL=https://minexis-backend-xxxx.onrender.com
   ```
3. Save the file
4. Commit and push:
   ```bash
   cd d:\SIH\minexis
   git add ui/dashboard/.env.production
   git commit -m "Configure production backend URL"
   git push origin main
   ```

---

## ✅ Step 4: Deploy Frontend to Vercel

### 4.1 Sign Up & Connect GitHub

1. Go to **https://vercel.com**
2. Click **"Sign Up"**
3. Sign up with your **GitHub account**
4. Authorize Vercel

### 4.2 Import Project

1. Click **"Add New..."** → **"Project"**
2. Find: **`hariom9617/minexis-source-code`**
3. Click **"Import"**

### 4.3 Configure Project

**Framework Preset:**
- Select: **Vite**

**Root Directory:**
- Click **"Edit"**
- Enter: `minexis/ui/dashboard`
- Click **"Continue"**

**Build Settings** (should auto-detect):
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install`

### 4.4 Add Environment Variable

Click **"Environment Variables"**

Add:
```
Name: VITE_API_BASE_URL
Value: https://your-actual-render-url.onrender.com
```

**CRITICAL:** Use your real Render backend URL from Step 2.5!

### 4.5 Deploy

1. Click **"Deploy"**
2. Wait 2-5 minutes
3. Once completed, click **"Visit"**
4. **Copy your frontend URL**:
   - Format: `https://minexis-dashboard-xxxx.vercel.app`

---

## ✅ Step 5: Update Backend CORS

Now that you have your Vercel URL, update the backend CORS settings:

### Option A: Via Render Dashboard (Recommended)

1. Go to Render Dashboard
2. Open your **minexis-backend** service
3. Go to **"Environment"** tab
4. Find `CORS_ORIGINS` variable
5. Update to: `https://your-frontend.vercel.app,http://localhost:3000`
6. Click **"Save Changes"**
7. Wait for automatic redeploy (~2 minutes)

### Option B: Via Code Update

1. Edit `d:\SIH\minexis\backend\app.py`
2. Find the CORS middleware section (around line 110)
3. Update `allow_origins` list:
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
   git commit -m "Update CORS for production frontend"
   git push origin main
   ```
5. Render will auto-redeploy

---

## ✅ Step 6: Final Testing

### 6.1 Test Frontend

1. Open your Vercel URL: `https://your-frontend.vercel.app`
2. Press **F12** to open Developer Tools
3. Check **Console** tab for errors
4. Check **Network** tab → filter **WS** (WebSocket)
   - Should see connection to backend
   - Status: **101 Switching Protocols** = ✅ Connected

### 6.2 Test Features

- [ ] Dashboard loads without errors
- [ ] Scenario buttons work (SAFE, CAUTION, WARNING, CRITICAL)
- [ ] Thermal Perception Panel shows webcam
- [ ] Radar Perception Panel shows SVG visualization
- [ ] Vehicle Trajectory Panel displays prediction
- [ ] Bottom cards show real-time data
- [ ] WebSocket stays connected (check Network tab)

### 6.3 Test on Multiple Devices

- [ ] Desktop Chrome
- [ ] Desktop Firefox
- [ ] Mobile browser
- [ ] Different network (mobile data)

---

## 📋 Your Deployment URLs

**Fill in after deployment:**

### Backend (Render)
```
https://___________________________________.onrender.com
```

### Frontend (Vercel)
```
https://___________________________________.vercel.app
```

---

## 🔧 Troubleshooting

### Issue: "git push" fails with authentication error

**Solution:**
```bash
# Use Personal Access Token as password
# Generate at: https://github.com/settings/tokens
git push -u origin main
# Username: hariom9617
# Password: <paste your token>
```

### Issue: Render shows "Application Error"

**Check:**
1. Render Dashboard → Logs tab
2. Verify Build Command: `pip install -r requirements.txt`
3. Verify Start Command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. Verify Root Directory: `minexis`

### Issue: Frontend shows "CORS policy blocked"

**Solution:**
1. Update `CORS_ORIGINS` in Render (Step 5)
2. Include your exact Vercel URL
3. Wait for Render to redeploy
4. Clear browser cache: `Ctrl + Shift + R`

### Issue: WebSocket connection failed

**Check:**
1. Backend health endpoint works: `https://your-backend.onrender.com/health`
2. Frontend `.env.production` has correct backend URL
3. CORS includes your Vercel domain
4. Check browser console for specific error

### Issue: Render free tier "cold start" delay

**Why:** Free tier spins down after 15 minutes of inactivity

**Solutions:**
- Accept 30s cold start for demos (mention in presentation)
- Use UptimeRobot to ping every 14 minutes (keeps it alive)
- Upgrade to Starter ($7/month) for instant response

---

## 🎬 Pre-Presentation Checklist

### 24 Hours Before

- [ ] Test complete user flow end-to-end
- [ ] Verify all scenarios work (SAFE → CRITICAL)
- [ ] Check WebSocket connection stability
- [ ] Test on different browsers
- [ ] Test on mobile device
- [ ] Take screenshots/recording as backup

### 1 Hour Before

- [ ] Visit site to wake up backend (if free tier)
- [ ] Open browser DevTools and check for errors
- [ ] Test scenario switching
- [ ] Verify all three perception panels load
- [ ] Keep local version ready as backup

### During Presentation

- [ ] Bookmark both URLs
- [ ] Keep DevTools open (shows real-time WebSocket)
- [ ] Demonstrate spotlight detection
- [ ] Show trajectory prediction
- [ ] Explain adaptive sensor fusion

---

## 💰 Cost Summary

### Current (Free Tier)
- **Render:** Free with cold starts
- **Vercel:** Free (hobby projects)
- **Total:** $0/month

**Limitations:**
- Backend spins down after 15 min inactivity
- First load: ~30s cold start
- 750 hours/month limit on Render

### Production (Paid)
- **Render Starter:** $7/month (no cold starts)
- **Vercel:** Free (or $20/mo Pro)
- **Total:** $7-27/month

---

## 🚀 Auto-Deploy (Already Configured!)

Both platforms now watch your GitHub `main` branch:

**To deploy updates:**
```bash
# Make changes
git add .
git commit -m "Your update message"
git push origin main
```

Both Render and Vercel will automatically rebuild and deploy!

---

## 📊 Monitoring

### Render (Backend)
- **Logs:** Dashboard → Your Service → Logs
- **Metrics:** CPU, Memory, Network usage
- **Events:** Deployment history

### Vercel (Frontend)
- **Analytics:** Dashboard → Analytics
- **Deployments:** Dashboard → Deployments
- **Logs:** Click any deployment → View Logs

### Recommended Tools
- **UptimeRobot** (uptimerobot.com) - Free uptime monitoring
- **Sentry** (sentry.io) - Error tracking
- **Google Analytics** - User analytics

---

## ✨ Deployment Complete!

Once all steps are done, your MINEXIS system will be live on the internet!

**Share your demo:**
- Frontend: `https://your-app.vercel.app`
- Backend: `https://your-app.onrender.com`

**For SIH 2026 presentation:**
1. Show live demo URL (internet-accessible)
2. Demonstrate real-time detection with webcam
3. Explain spotlight detection system
4. Show trajectory prediction (3-second linear)
5. Switch scenarios to demonstrate different risk states
6. Highlight professional deployment on industry platforms

**Good luck with Smart India Hackathon! 🏆**

---

## 📞 Support Resources

**Render:**
- Docs: https://render.com/docs
- Status: https://status.render.com
- Discord: https://discord.gg/render

**Vercel:**
- Docs: https://vercel.com/docs
- Help: https://vercel.com/help
- Discord: https://vercel.com/discord

**MINEXIS:**
- Full Guide: `RENDER_VERCEL_DEPLOYMENT.md`
- Architecture: `README.md`
- Dashboard Refactor: `DASHBOARD_REFACTOR_REPORT.md`

---
