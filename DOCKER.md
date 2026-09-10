# Docker & Kubernetes Deployment Guide

## Build Docker Image Locally

```bash
cd position-sizing-bot
docker build -t position-sizing-bot:latest .
```

**Test locally:**
```bash
docker run -e TELEGRAM_BOT_TOKEN=your_token_here \
           -e RAILWAY_PUBLIC_DOMAIN=localhost:8080 \
           -e PORT=8080 \
           -p 8080:8080 \
           position-sizing-bot:latest
```

## Push to Docker Hub

1. Login:
```bash
docker login
```

2. Tag image:
```bash
docker tag position-sizing-bot:latest zulkifle/position-sizing-bot:latest
```

3. Push:
```bash
docker push zulkifle/position-sizing-bot:latest
```

Replace `zulkifle` with your Docker Hub username.

## Deploy to Kubernetes

### Prerequisites
- K8s cluster running (minikube, K3s, or cloud)
- `kubectl` configured
- `position-sizing-bot` image pushed to Docker Hub

### Steps

1. **Create namespace (optional):**
```bash
kubectl create namespace bots
```

2. **Create secret for bot token:**
```bash
kubectl create secret generic telegram-secret \
  --from-literal=bot-token=YOUR_BOT_TOKEN_HERE \
  -n default
```

3. **Update k8s-deployment.yaml:**
   - Replace `zulkifle` with your Docker Hub username
   - Replace `position-sizing-bot.YOUR_DOMAIN.com` with your actual domain
   - Replace `YOUR_BOT_TOKEN_HERE` if not using secret

4. **Deploy:**
```bash
kubectl apply -f k8s-deployment.yaml
```

5. **Verify:**
```bash
kubectl get pods
kubectl logs -f deployment/position-sizing-bot
```

6. **Get service IP:**
```bash
kubectl get service position-sizing-bot
# Note the EXTERNAL-IP
```

7. **Set Telegram webhook:**
```bash
curl -X POST https://api.telegram.org/botTOKEN/setWebhook \
  -d url=http://YOUR_EXTERNAL_IP/TOKEN
```

## Scaling

Scale to 2 replicas:
```bash
kubectl scale deployment position-sizing-bot --replicas=2
```

## Cleanup

Remove deployment:
```bash
kubectl delete -f k8s-deployment.yaml
```

Or:
```bash
kubectl delete deployment position-sizing-bot
kubectl delete service position-sizing-bot
```

## CKA Learning Path

This deployment teaches:
- ✅ Dockerfile best practices (multi-stage builds, health checks)
- ✅ K8s Deployment management
- ✅ Secret handling (ConfigMaps, Secrets)
- ✅ Service exposure (LoadBalancer, Ingress)
- ✅ Resource limits & requests
- ✅ Pod lifecycle (livenessProbe)
- ✅ kubectl commands

Perfect for CKA exam prep! 📚
