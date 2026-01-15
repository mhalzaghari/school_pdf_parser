# Deployment Guide

This guide covers deploying the BDI-3 PDF to Word Converter to various platforms.

## Quick Deploy Options

### 1. Railway (Recommended - Easiest)

Railway offers free hosting with automatic deployments from GitHub.

**Steps:**

1. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Deploy to Railway**
   - Go to [Railway](https://railway.app)
   - Click "New Project" → "Deploy from GitHub repo"
   - Select your repository
   - Railway will auto-detect the Dockerfile and deploy
   - Your app will be live at: `https://your-app.railway.app`

3. **Custom Domain (Optional)**
   - In Railway dashboard, go to Settings → Domains
   - Add your custom domain

**Cost:** Free tier includes 500 hours/month

---

### 2. Render

Render provides free web services with automatic SSL.

**Steps:**

1. **Push to GitHub** (same as above)

2. **Deploy to Render**
   - Go to [Render](https://render.com)
   - Click "New" → "Web Service"
   - Connect your GitHub repository
   - Configure:
     - **Environment:** Docker
     - **Region:** Choose closest to your users
     - **Instance Type:** Free
   - Click "Create Web Service"
   - Your app will be live at: `https://your-app.onrender.com`

**Cost:** Free tier available (spins down after inactivity)

---

### 3. Fly.io

Fly.io offers global deployment with excellent performance.

**Steps:**

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login and Launch**
   ```bash
   fly auth login
   fly launch
   ```

3. **Follow prompts:**
   - Choose app name
   - Select region
   - Don't add PostgreSQL or Redis
   - Deploy now? Yes

4. **Your app will be live at:** `https://your-app.fly.dev`

**Cost:** Free tier includes 3 shared VMs

---

### 4. Heroku

Classic platform with easy deployment.

**Steps:**

1. **Install Heroku CLI**
   ```bash
   brew install heroku/brew/heroku  # macOS
   ```

2. **Create heroku.yml** (already included in project)

3. **Deploy**
   ```bash
   heroku login
   heroku create your-app-name
   heroku stack:set container
   git push heroku main
   ```

4. **Your app will be live at:** `https://your-app-name.herokuapp.com`

**Cost:** Free tier discontinued, starts at $5/month

---

## Environment Variables

No environment variables are required for basic operation. The app works out of the box.

---

## Custom Domain Setup

### Railway
1. Dashboard → Settings → Domains → Add Custom Domain
2. Add CNAME record: `your-domain.com` → `your-app.railway.app`

### Render
1. Dashboard → Settings → Custom Domain
2. Add CNAME record: `your-domain.com` → `your-app.onrender.com`

### Fly.io
```bash
fly certs add your-domain.com
```
Then add DNS records as instructed.

---

## Monitoring & Logs

### Railway
- Dashboard → Deployments → View Logs

### Render
- Dashboard → Logs tab

### Fly.io
```bash
fly logs
```

---

## Scaling

All platforms support easy scaling:

- **Railway:** Dashboard → Settings → Scale
- **Render:** Dashboard → Settings → Instance Type
- **Fly.io:** `fly scale count 2` (2 instances)

---

## Troubleshooting

### PDF Parsing Fails
- Ensure PDF is a valid BDI-3 Family Report
- Check that pages 4-13 contain Item Level Scores
- Verify PDF is not password-protected

### Deployment Fails
- Check build logs for errors
- Ensure Dockerfile is in root directory
- Verify requirements.txt has all dependencies

### App is Slow
- Free tiers may have cold starts (15-30 seconds)
- Upgrade to paid tier for always-on instances
- Consider using a CDN for static files

---

## Security Notes

- The app does not store uploaded PDFs
- All processing happens in memory
- Generated Word docs are sent directly to user
- No database or persistent storage required

---

## Cost Comparison

| Platform | Free Tier | Paid Tier | Best For |
|----------|-----------|-----------|----------|
| Railway | 500 hrs/mo | $5/mo | Easy deployment |
| Render | Yes (sleeps) | $7/mo | Simple apps |
| Fly.io | 3 VMs | $1.94/mo | Global reach |
| Heroku | No | $5/mo | Enterprise |

---

## Recommended: Railway

For this use case, **Railway** is recommended because:
- ✅ Free tier is generous
- ✅ No cold starts
- ✅ Automatic deployments from GitHub
- ✅ Easy custom domain setup
- ✅ Great for sharing with one person

---

## Share with Your Friend

Once deployed, simply share the URL:
```
https://your-app.railway.app
```

She can:
1. Visit the URL
2. Upload her BDI-3 PDF
3. Click "Convert"
4. Download the formatted Word document

No account or login required!

