# Docker Deployment Guide

This guide explains how to build and run the Restaurant Analytics Agent using Docker.

## Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (usually included with Docker Desktop)
- Environment variables configured

## Quick Start

### 1. Create Environment File

Create a `.env` file in the root directory (`clave-take-home/`):

```bash
# Database Configuration
SUPABASE_DB_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres
# OR use separate variables:
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_PASSWORD=your_password

# LLM Provider
LLM_PROVIDER=nvidia  # or "grok"

# NVIDIA API (if using NVIDIA)
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_MODEL=ai-nemotron-3-nano-30b-a3b

# Grok/XAI API (if using Grok)
GROK_API_KEY=your_grok_api_key
GROK_MODEL=grok-2
GROK_BASE_URL=https://api.x.ai/v1

# JWT Authentication
JWT_SECRET_KEY=your_secret_key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Frontend API URL (should point to backend service)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional Settings
LOG_LEVEL=INFO
MAX_QUERY_TIMEOUT=30
MAX_RETRIES=2
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
```

### 2. Build and Run with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Individual Service Deployment

### Backend Only

```bash
cd restaurant-analytics-agent

# Build the image
docker build -t restaurant-analytics-backend .

# Run the container
docker run -d \
  --name restaurant-analytics-backend \
  -p 8000:8000 \
  --env-file ../.env \
  restaurant-analytics-backend

# View logs
docker logs -f restaurant-analytics-backend
```

### Frontend Only

```bash
cd frontend

# Build the image
docker build -t restaurant-analytics-frontend .

# Run the container
docker run -d \
  --name restaurant-analytics-frontend \
  -p 3000:3000 \
  -e NEXT_PUBLIC_API_URL=http://localhost:8000 \
  restaurant-analytics-frontend

# View logs
docker logs -f restaurant-analytics-frontend
```

## Docker Compose Commands

```bash
# Build images
docker-compose build

# Start services in detached mode
docker-compose up -d

# Start services and view logs
docker-compose up

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# Rebuild and restart
docker-compose up -d --build

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend

# Execute command in container
docker-compose exec backend python -m pytest
docker-compose exec frontend npm run lint

# Restart a specific service
docker-compose restart backend
docker-compose restart frontend
```

## Production Deployment

### 1. Update Environment Variables

For production, update `.env` with production values:
- Use production database URL
- Set secure JWT secret key
- Configure production API URLs
- Set appropriate log levels

### 2. Build Production Images

```bash
# Build with no cache for clean build
docker-compose build --no-cache

# Tag images for registry (optional)
docker tag restaurant-analytics-backend your-registry/restaurant-analytics-backend:latest
docker tag restaurant-analytics-frontend your-registry/restaurant-analytics-frontend:latest
```

### 3. Push to Registry (Optional)

```bash
# Login to registry
docker login your-registry.com

# Push images
docker push your-registry/restaurant-analytics-backend:latest
docker push your-registry/restaurant-analytics-frontend:latest
```

### 4. Deploy to Production Server

```bash
# On production server, pull images and run
docker-compose pull
docker-compose up -d
```

## Health Checks

Both services include health checks:

- **Backend**: `GET /api/health`
- **Frontend**: Container health check via HTTP

Check health status:
```bash
# Backend health
curl http://localhost:8000/api/health

# Container health
docker-compose ps
```

## Troubleshooting

### Issue: Frontend can't connect to backend

**Solution**: 
- Ensure `NEXT_PUBLIC_API_URL` is set correctly
- If using Docker Compose, use service name: `http://backend:8000`
- For external access, use host IP or domain

### Issue: Database connection errors

**Solution**:
- Verify `SUPABASE_DB_URL` is correct
- Check if database allows connections from Docker network
- Ensure database is accessible from container

### Issue: Build fails

**Solution**:
- Check Dockerfile syntax
- Verify all dependencies are in `requirements.txt` or `package.json`
- Clear Docker cache: `docker system prune -a`

### Issue: Port already in use

**Solution**:
- Change ports in `docker-compose.yml`
- Or stop conflicting services:
  ```bash
  # Find process using port
  lsof -i :8000
  lsof -i :3000
  
  # Kill process or change port
  ```

### Issue: Permission errors

**Solution**:
- Ensure Docker has proper permissions
- Check file ownership in containers
- Review Dockerfile USER directives

## Development with Docker

### Hot Reload (Development)

For development with hot reload, you can mount volumes:

```yaml
# Add to docker-compose.yml services
volumes:
  - ./backend:/app
  - ./frontend:/app
```

Then run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Debugging

```bash
# Access container shell
docker-compose exec backend bash
docker-compose exec frontend sh

# View environment variables
docker-compose exec backend env

# Check network connectivity
docker-compose exec backend ping frontend
docker-compose exec frontend ping backend
```

## Image Sizes

- **Backend**: ~500-800 MB (includes Python, dependencies)
- **Frontend**: ~200-400 MB (includes Node.js, Next.js)

To reduce image sizes:
- Use multi-stage builds (already implemented)
- Remove dev dependencies in production
- Use Alpine Linux base images (already used)

## Security Best Practices

1. **Use non-root users** (already implemented)
2. **Keep images updated**: Regularly rebuild with latest base images
3. **Scan for vulnerabilities**: 
   ```bash
   docker scan restaurant-analytics-backend
   docker scan restaurant-analytics-frontend
   ```
4. **Limit resources**: Add resource limits in `docker-compose.yml`
5. **Use secrets**: For production, use Docker secrets or external secret management

## Resource Limits

Add to `docker-compose.yml` if needed:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## Monitoring

```bash
# View resource usage
docker stats

# View container details
docker inspect restaurant-analytics-backend
docker inspect restaurant-analytics-frontend
```

## Cleanup

```bash
# Remove stopped containers
docker-compose down

# Remove images
docker rmi restaurant-analytics-backend restaurant-analytics-frontend

# Clean up everything
docker system prune -a
```

