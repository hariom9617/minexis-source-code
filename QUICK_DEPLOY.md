# MINEXIS Quick Deploy Reference

**🚀 Ultra-Fast Deployment Guide**

---

## Step 1: Push to GitHub (NOW)

```bash
cd d:\SIH\minexis
git push -u origin main
```

If asked for password, use GitHub **Personal Access Token** (not password).  
Generate at: https://github.com/settings/tokens

---

## Step 2: Render Backend (5 minutes)

1. **Sign up:** https://render.com → Sign in with GitHub
2. **Create Web Service** → Connect `hariom9617/minexis-source-code`
3. **Configure:**
   ```
   Name: minexis-backend
   Root Directory: minexis
   Build: pip install -r requirements.txt
   Start: uvicorn backend.app:app --host 0.0.0.0 --port $PORT
   ```
4. **Environment Variables:**
   ```
   PYTHON_VERSION=3.11
   CORS_ORIGINS=*
   ```
5. **Deploy** → Wait 5-10 min → **COPY YOUR URL**

**Test:** Open `https://your-backend.onrender.com/health`

---

## Step 3: Update Frontend Config

```bash
# Edit ui/dashboard/.env.production
VITE_API_BASE_URL=https://your-actual-backend.onrender.com

# Push update
git add ui/dashboard/.env.production
git commit -m "Configure production backend"
git push origin main
```

---

## Step 4: Vercel Frontend (3 minutes)

1. **Sign up:** https://vercel.com → Sign in with GitHub
2. **Import Project** → Select `hariom9617/minexis-source-code`
3. **Configure:**
   ```
   Framework: Vite
   Root Directory: minexis/ui/dashboard
   Build: npm run build
   Output: dist
   ```
4. **Environment Variable:**
   ```
   VITE_API_BASE_URL=https://your-backend.onrender.com
   ```
5. **Deploy** → Wait 2-3 min → **COPY YOUR URL**

---

## Step 5: Fix CORS

**Render Dashboard** → Your Service → Environment → Edit `CORS_ORIGINS`:
```
https://your-frontend.vercel.app,http://localhost:3000
```

Save → Auto-redeploys in 2 minutes.

---

## ✅ Done!

Open: `https://your-frontend.vercel.app`

Press **F12** → Check Console → Should see WebSocket connected.

Test all scenario buttons: SAFE, CAUTION, WARNING, CRITICAL

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Git push fails | Use Personal Access Token as password |
| Render build fails | Check logs, verify root directory is `minexis` |
| CORS error | Update CORS_ORIGINS with exact Vercel URL |
| WebSocket fails | Check .env.production has correct backend URL |
| Slow first load | Free tier spins down - visit site 1hr before demo |

---

## 📋 Your URLs

**Backend:**  
https://___________________________________.onrender.com

**Frontend:**  
https://___________________________________.vercel.app

---

**Full Details:** See `DEPLOYMENT_CHECKLIST.md` and `RENDER_VERCEL_DEPLOYMENT.md`
