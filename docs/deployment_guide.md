# DriftSentinel Deployment Guide

This guide details exactly how to push your code to GitHub and host your production inference service on **Render**.

## 1. GitHub Setup 🛡️

### Step A: Initialize Git locally
If you haven't already initialized git:
```bash
git init
git add .
git commit -m "Initial commit: Modular structure with Kafka streaming"
```

### Step B: Create a repository on GitHub
1. Go to [github.com/new](https://github.com/new).
2. Name it `DriftSentinel`.
3. Do **not** initialize with README or License (you already have them).

### Step C: Push to GitHub
```bash
git remote add origin https://github.com/YOUR_USERNAME/DriftSentinel.git
git branch -M main
git push -u origin main
```

---

## 2. Render Deployment (Web Service) 🚀

Render allows you to deploy Dockerized apps directly.

### Step 1: Create a New Web Service
1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Click **New +** > **Web Service**.
3. Connect your **DriftSentinel** GitHub repository.

### Step 2: Configure Service Settings
- **Name**: `drift-sentinel-api`
- **Region**: (Choose closest to you)
- **Branch**: `main`
- **Runtime**: `Docker`

### Step 3: Set Advanced Build Settings
- **Dockerfile Path**: `infra/docker/Dockerfile`
- **Docker Context**: `.` (The root of the repo)

### Step 4: Add Environment Variables
Add these to ensure the app starts correctly in a cloud environment:
- `KAFKA_ENABLED`: `false` (Unless you have a managed Kafka URI to provide).
- `PORT`: `8000` (FastAPI needs to know what port Render expects).

### Step 5: Deploy!
Render will now pull your code, build the Docker image, and expose your API. You can monitor the logs directly in the Render dashboard.

---

## 3. Kafka & Monitoring (Next Phase) 📊
For the full drift detection pipeline to work on Render, you should eventually:
1. Provision a managed Kafka instance (e.g., [Upstash Kafka](https://upstash.com/kafka)).
2. Update the `KAFKA_URL` and `KAFKA_ENABLED=true` environment variables on Render.
3. Deploy the `monitoring-service` (Week 2) as a separate Render background worker.

---

## ✅ Deployment Checklist
- [ ] API is publicly accessible at `https://your-app.onrender.com/docs`
- [ ] Logs show "Model loaded successfully"
- [ ] `/predict` endpoint returns valid JSON response
