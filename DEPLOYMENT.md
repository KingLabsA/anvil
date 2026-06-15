# Anvil Deployment Guide

This guide covers all deployment options for Anvil, from local development to production deployment.

## Quick Start

### Local Installation (Recommended for Personal Use)

```bash
# One-liner install
curl -fsSL https://raw.githubusercontent.com/KingLabsA/anvil/main/install.sh | bash

# Or install manually
pip install fableforge-anvil-agent[all]

# Start the web UI
anvil serve
```

### Docker Deployment (Recommended for Teams)

```bash
# Clone the repository
git clone https://github.com/KingLabsA/anvil.git
cd anvil

# Start with Docker Compose
docker-compose up -d

# Access the web UI
open http://localhost:8000
```

## Deployment Options

### 1. Local Development

**Best for:** Personal use, development, testing

```bash
# Install
pip install fableforge-anvil-agent[all]

# Run tasks
anvil run "Your task here"

# Start web UI
anvil serve --port 8000
```

**Pros:**
- Simple setup
- No server required
- Full control

**Cons:**
- Single user
- Requires local resources

### 2. Docker (Local)

**Best for:** Team use on a shared machine, isolated environment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

**Configuration:**

Create a `.env` file:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

**Pros:**
- Isolated environment
- Easy to manage
- Reproducible

**Cons:**
- Still single machine
- Requires Docker

### 3. VPS/Cloud Deployment

**Best for:** Team access, production use, 24/7 availability

#### Option A: DigitalOcean/AWS/GCP VM

```bash
# SSH into your server
ssh user@your-server.com

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone and deploy
git clone https://github.com/KingLabsA/anvil.git
cd anvil

# Create .env file
cat > .env << EOF
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
EOF

# Start
docker-compose up -d

# Set up reverse proxy (nginx)
sudo apt install nginx
sudo nano /etc/nginx/sites-available/anvil
```

Nginx configuration:
```nginx
server {
    listen 80;
    server_name anvil.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/anvil /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Set up SSL with Let's Encrypt
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d anvil.yourdomain.com
```

#### Option B: Railway/Render/Fly.io (PaaS)

**Railway:**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and init
railway login
railway init

# Set environment variables
railway variables set OPENAI_API_KEY=sk-...

# Deploy
railway up
```

**Render:**
1. Connect your GitHub repo
2. Create a new Web Service
3. Set build command: `docker build -t anvil .`
4. Set start command: `docker run -p $PORT:8000 anvil`
5. Add environment variables
6. Deploy

#### Option C: Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: anvil
spec:
  replicas: 2
  selector:
    matchLabels:
      app: anvil
  template:
    metadata:
      labels:
        app: anvil
    spec:
      containers:
      - name: anvil
        image: your-registry/anvil:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: anvil-secrets
              key: openai-api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: anvil-service
spec:
  selector:
    app: anvil
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

Deploy:
```bash
kubectl apply -f k8s-deployment.yaml
```

## Production Considerations

### Authentication

**Important:** The web UI currently has no authentication. For production deployment, add authentication:

#### Option 1: Nginx Basic Auth

```bash
# Create password file
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Update nginx config
location / {
    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    proxy_pass http://localhost:8000;
    # ... rest of config
}
```

#### Option 2: Cloudflare Access

1. Add your domain to Cloudflare
2. Enable Cloudflare Access
3. Configure authentication (Google, GitHub, etc.)
4. Route traffic through Cloudflare

#### Option 3: OAuth2 Proxy

```bash
# Install oauth2-proxy
docker run -d \
  --name oauth2-proxy \
  -p 4180:4180 \
  quay.io/oauth2-proxy/oauth2-proxy:v7.4.0 \
  --provider=github \
  --client-id=YOUR_CLIENT_ID \
  --client-secret=YOUR_CLIENT_SECRET \
  --cookie-secret=YOUR_COOKIE_SECRET \
  --upstream=http://anvil:8000 \
  --email-domain=yourdomain.com
```

### Rate Limiting

Add rate limiting with Nginx:

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    location / {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://localhost:8000;
        # ... rest of config
    }
}
```

### Monitoring

#### Health Checks

The web UI includes a health endpoint:
```bash
curl http://localhost:8000/health
```

#### Logging

View logs:
```bash
# Docker
docker-compose logs -f anvil

# Direct
journalctl -u anvil -f
```

#### Metrics (Optional)

Add Prometheus metrics endpoint (requires code changes):
```python
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter('anvil_requests_total', 'Total requests')
REQUEST_DURATION = Histogram('anvil_request_duration_seconds', 'Request duration')
```

### Backup

Backup Anvil data:
```bash
# Docker volume
docker run --rm -v anvil_anvil-data:/data -v $(pwd):/backup alpine \
  tar czf /backup/anvil-backup-$(date +%Y%m%d).tar.gz /data

# Direct installation
tar czf anvil-backup-$(date +%Y%m%d).tar.gz ~/.anvil
```

Restore:
```bash
# Docker volume
docker run --rm -v anvil_anvil-data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/anvil-backup-YYYYMMDD.tar.gz -C /

# Direct installation
tar xzf anvil-backup-YYYYMMDD.tar.gz -C ~
```

### Updates

```bash
# Docker
docker-compose pull
docker-compose up -d

# Direct installation
pip install --upgrade fableforge-anvil-agent[all]
```

## Resource Requirements

### Minimum
- CPU: 1 core
- RAM: 1 GB
- Disk: 500 MB
- Network: 10 Mbps

### Recommended
- CPU: 2 cores
- RAM: 4 GB
- Disk: 2 GB
- Network: 100 Mbps

### High Load (10+ concurrent users)
- CPU: 4+ cores
- RAM: 8+ GB
- Disk: 10+ GB
- Network: 1 Gbps

## Security Checklist

- [ ] Enable authentication (Nginx basic auth, OAuth2, etc.)
- [ ] Use HTTPS (Let's Encrypt)
- [ ] Set up firewall (ufw, iptables)
- [ ] Regular updates
- [ ] API key rotation
- [ ] Backup strategy
- [ ] Rate limiting
- [ ] Logging and monitoring
- [ ] Network isolation (VPC, private network)
- [ ] Secrets management (not in code/config files)

## Troubleshooting

### Port already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill it
kill -9 <PID>

# Or use a different port
anvil serve --port 8001
```

### Docker permission denied
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Out of memory
```bash
# Check memory usage
free -h

# Increase swap
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Connection refused
```bash
# Check if service is running
docker-compose ps

# Check logs
docker-compose logs anvil

# Check firewall
sudo ufw status
sudo ufw allow 8000/tcp
```

## Support

- GitHub Issues: https://github.com/KingLabsA/anvil/issues
- Documentation: https://github.com/KingLabsA/anvil#readme
- Discord: [Coming soon]

## License

MIT License - See LICENSE file for details
