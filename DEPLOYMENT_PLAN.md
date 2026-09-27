# MINEXIS Deployment Plan

**Project:** MINEXIS — Intelligent Mine Vehicle Safety System  
**Repository:** https://github.com/hariom9617/minexis-source-code.git  
**Status:** Ready for Deployment

---

## Deployment Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    MINEXIS System                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐         ┌─────────────────────┐      │
│  │  Frontend        │◄────────┤  Backend API        │      │
│  │  (React/Vite)    │  HTTP   │  (FastAPI/Python)   │      │
│  │  Dashboard UI    │  WS     │  Pipeline Engine    │      │
│  └──────────────────┘         └─────────────────────┘      │
│         │                              │                    │
│         │                              │                    │
│         ▼                              ▼                    │
│  ┌──────────────────┐         ┌─────────────────────┐      │
│  │  Static Hosting  │         │  Python Runtime     │      │
│  │  (Vercel/Netlify)│         │  (Railway/Render)   │      │
│  └──────────────────┘         └─────────────────────┘      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Recommended Deployment Platforms

### **Option 1: Railway + Vercel (RECOMMENDED)** ⭐

#### Backend → Railway
- **Why:** Excellent Python support, WebSocket compatible, free tier available
- **Features:** Auto-deploy from GitHub, environment variables, persistent storage
- **Cost:** Free tier: 500 hours/month, then $5/month
- **WebSocket:** ✅ Fully supported

#### Frontend → Vercel
- **Why:** Best for React/Vite apps, global CDN, instant deployments
- **Features:** Auto-deploy from GitHub, preview deployments, analytics
- **Cost:** Free for hobby projects
- **Performance:** ✅ Excellent (global edge network)

---

### **Option 2: Render (ALL-IN-ONE)**

#### Backend + Frontend → Render
- **Why:** Single platform for both, simpler management
- **Features:** Auto-deploy, free SSL, custom domains
- **Cost:** Free tier with limitations (spins down after inactivity)
- **WebSocket:** ✅ Supported
- **Note:** Free tier has cold starts (30s delay when idle)

---

### **Option 3: Heroku (CLASSIC)**

#### Backend + Frontend → Heroku
- **Why:** Mature platform, good documentation
- **Features:** Add-ons ecosystem, CI/CD integration
- **Cost:** Free tier discontinued (starts at $7/month)
- **WebSocket:** ✅ Supported with specific configuration

---

### **Option 4: Self-Hosted VPS**

#### DigitalOcean / Linode / AWS EC2
- **Why:** Full control, custom configuration
- **Cost:** Starting $5-10/month
- **Setup:** Requires manual server configuration
- **Best for:** Production deployments, scaling needs

---

## Detailed Deployment Steps

### **RECOMMENDED: Railway + Vercel Setup**

---

### **Part 1: Deploy Backend to Railway**

#### Step 1: Prepare Backend for Deployment

**Create `railway.json`:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "uvicorn backend.app:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**Create `Procfile` (backup):**
```
web: uvicorn backend.app:app --host 0.0.0.0 --port $PORT
```

**Update `backend/app.py` to use environment PORT:**
```python
import os

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port)
```

#### Step 2: Deploy to Railway

1. **Sign up:** https://railway.app (use GitHub account)
2. **Create New Project** → "Deploy from GitHub repo"
3. **Select:** `hariom9617/minexis-source-code`
4. **Root Directory:** Set to `/minexis` (if needed)
5. **Environment Variables:**
   ```
   PYTHON_VERSION=3.11
   PORT=8000
   CORS_ORIGINS=*
   ```
6. **Deploy:** Railway will auto-detect Python and deploy
7. **Get URL:** Copy your Railway app URL (e.g., `https://minexis-backend.railway.app`)

#### Step 3: Configure CORS

Update `backend/app.py` to allow your frontend domain:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend.vercel.app", "*"],  # Update after frontend deploy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### **Part 2: Deploy Frontend to Vercel**

#### Step 1: Update Frontend Configuration

**Create `.env.production` in `ui/dashboard/`:**
```env
VITE_API_BASE_URL=https://your-railway-app.railway.app
```

**Update `vite.config.ts` if needed:**
```typescript
export default defineConfig({
  plugins: [react()],
  base: '/',
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
})
```

#### Step 2: Deploy to Vercel

1. **Sign up:** https://vercel.com (use GitHub account)
2. **Import Project** → Select `hariom9617/minexis-source-code`
3. **Framework:** Vite
4. **Root Directory:** `minexis/ui/dashboard`
5. **Build Command:** `npm run build`
6. **Output Directory:** `dist`
7. **Environment Variables:**
   ```
   VITE_API_BASE_URL=https://your-railway-app.railway.app
   ```
8. **Deploy:** Vercel will build and deploy automatically
9. **Get URL:** Copy your Vercel URL (e.g., `https://minexis-dashboard.vercel.app`)

#### Step 3: Update Backend CORS

Go back to Railway and update the `CORS_ORIGINS` environment variable:
```
CORS_ORIGINS=https://minexis-dashboard.vercel.app,http://localhost:3000
```

---

## Alternative Platform Instructions

### **Deploy to Render (All-in-One)**

#### Backend Service

1. **Sign up:** https://render.com
2. **New Web Service** → Connect GitHub repo
3. **Settings:**
   - **Name:** minexis-backend
   - **Root Directory:** `minexis`
   - **Runtime:** Python 3.11
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables:**
   ```
   PYTHON_VERSION=3.11
   PORT=10000
   ```
5. **Deploy**

#### Frontend Service

1. **New Static Site** → Connect same repo
2. **Settings:**
   - **Name:** minexis-dashboard
   - **Root Directory:** `minexis/ui/dashboard`
   - **Build Command:** `npm install && npm run build`
   - **Publish Directory:** `dist`
3. **Environment Variables:**
   ```
   VITE_API_BASE_URL=https://minexis-backend.onrender.com
   ```
4. **Deploy**

---

## Pre-Deployment Checklist

### Backend Requirements

- [ ] Python dependencies in `requirements.txt`
- [ ] FastAPI CORS configured for frontend domain
- [ ] WebSocket endpoint `/ws/live` functional
- [ ] Health check endpoint `/health` added
- [ ] Environment variables documented
- [ ] PORT environment variable handled
- [ ] Static file serving disabled (frontend separate)

### Frontend Requirements

- [ ] Build command works locally (`npm run build`)
- [ ] Environment variables configured (`.env.production`)
- [ ] API base URL points to backend
- [ ] WebSocket URL derived from API base URL
- [ ] Build output in `dist/` directory
- [ ] No hardcoded `localhost` references
- [ ] Assets and routes configured for production

---

## Environment Variables Reference

### Backend (Railway/Render)
```env
PYTHON_VERSION=3.11
PORT=8000  # Or $PORT for dynamic assignment
CORS_ORIGINS=https://your-frontend-domain.com
LOG_LEVEL=INFO
```

### Frontend (Vercel/Netlify)
```env
VITE_API_BASE_URL=https://your-backend-domain.com
```

---

## Post-Deployment Testing

### 1. Backend Health Check
```bash
curl https://your-backend.railway.app/health
# Expected: {"status": "healthy"}
```

### 2. WebSocket Connection
```javascript
const ws = new WebSocket('wss://your-backend.railway.app/ws/live');
ws.onopen = () => console.log('Connected');
```

### 3. Frontend Load Test
- Open browser to `https://your-frontend.vercel.app`
- Check browser console for errors
- Verify WebSocket connection in Network tab
- Test all scenario buttons
- Verify real-time data updates

---

## Custom Domain Setup (Optional)

### Vercel (Frontend)
1. Go to Project Settings → Domains
2. Add your custom domain (e.g., `minexis.yourdomain.com`)
3. Update DNS records as instructed by Vercel
4. Wait for SSL certificate (automatic)

### Railway (Backend)
1. Go to Settings → Networking
2. Add custom domain (e.g., `api.minexis.yourdomain.com`)
3. Update DNS CNAME record
4. SSL certificate automatically provisioned

---

## Monitoring & Maintenance

### Railway Monitoring
- **Dashboard:** View logs, metrics, deployments
- **Logs:** Real-time logging in Railway dashboard
- **Alerts:** Set up for service downtime

### Vercel Analytics
- **Performance:** Page load times, Core Web Vitals
- **Traffic:** Visitor analytics
- **Errors:** Runtime error tracking

### Recommended Tools
- **Sentry:** Error tracking (sentry.io)
- **LogRocket:** Session replay (logrocket.com)
- **Uptime Robot:** Uptime monitoring (uptimerobot.com)

---

## Cost Estimation

### Free Tier (Hobby/Demo)
- **Railway:** Free 500 hours/month (≈20 days)
- **Vercel:** Unlimited hobby projects
- **Total:** $0/month (with limitations)

### Paid Tier (Production)
- **Railway:** $5/month (pay-as-you-go)
- **Vercel:** Free (or $20/month Pro)
- **Custom Domain:** $10-15/year
- **Total:** ~$5-25/month

---

## Troubleshooting

### Backend Not Starting
- Check Railway logs: `Railway Dashboard → Deployments → Logs`
- Verify Python version: `PYTHON_VERSION=3.11`
- Check dependencies: All in `requirements.txt`?
- Verify start command: `uvicorn backend.app:app --host 0.0.0.0 --port $PORT`

### WebSocket Connection Failed
- Ensure backend uses `wss://` (secure WebSocket)
- Check CORS headers include frontend domain
- Verify `/ws/live` endpoint is accessible
- Check Railway WebSocket support is enabled

### Frontend Build Failed
- Run `npm run build` locally to test
- Check Node.js version (16+ required)
- Verify all dependencies in `package.json`
- Check for TypeScript errors

### CORS Errors
- Update backend `CORS_ORIGINS` to include frontend URL
- Ensure both HTTP and HTTPS versions included
- Check browser console for specific error
- Verify wildcard `*` for development (not production)

---

## GitHub Repository Structure

```
minexis-source-code/
├── minexis/
│   ├── backend/          # FastAPI backend
│   ├── ui/dashboard/     # React frontend
│   ├── pipeline.py       # Core pipeline
│   ├── requirements.txt  # Python deps
│   ├── railway.json      # Railway config
│   └── Procfile          # Process file
├── README.md
├── DEPLOYMENT_PLAN.md
└── .gitignore
```

---

## Quick Start Commands

### Push to GitHub
```bash
cd d:\SIH\minexis
git init
git add .
git commit -m "Initial commit: MINEXIS complete system"
git branch -M main
git remote add origin https://github.com/hariom9617/minexis-source-code.git
git push -u origin main
```

### Build Locally (Test Before Deploy)
```bash
# Backend
cd minexis
pip install -r requirements.txt
uvicorn backend.app:app --reload

# Frontend
cd ui/dashboard
npm install
npm run build
npm run preview
```

---

## Success Criteria

✅ Backend deployed and responding to HTTP requests  
✅ WebSocket connection establishes successfully  
✅ Frontend loads without errors  
✅ Real-time data flows from backend to frontend  
✅ All three perception panels render correctly  
✅ Scenario buttons trigger backend updates  
✅ No CORS errors in browser console  
✅ Mobile responsive (bonus)  
✅ SSL/HTTPS enabled on both services  

---

## Support & Resources

### Documentation
- **Railway:** https://docs.railway.app
- **Vercel:** https://vercel.com/docs
- **FastAPI:** https://fastapi.tiangolo.com
- **Vite:** https://vitejs.dev

### Community
- **Railway Discord:** https://discord.gg/railway
- **Vercel Discord:** https://vercel.com/discord

---

## Next Steps After Deployment

1. **Share URLs:**
   - Frontend: `https://minexis-dashboard.vercel.app`
   - Backend: `https://minexis-backend.railway.app`

2. **Add to README:**
   - Live demo links
   - Deployment status badges
   - Architecture diagram

3. **Prepare for Hackathon:**
   - Test on presentation machine
   - Prepare backup (local deployment)
   - Create demo video
   - Document known limitations

---

**Deployment Status:** 🚀 READY TO DEPLOY

**Estimated Deployment Time:** 15-30 minutes

**Recommended Platform:** Railway (Backend) + Vercel (Frontend)

---

