# Vercel Deployment Guide

This guide explains how to deploy the Restaurant Analytics Agent backend to Vercel.

## Prerequisites

1. A Vercel account (sign up at [vercel.com](https://vercel.com))
2. Vercel CLI installed: `npm i -g vercel`
3. All required environment variables configured

## Deployment Steps

### 1. Install Vercel CLI (if not already installed)
```bash
npm i -g vercel
```

### 2. Login to Vercel
```bash
vercel login
```

### 3. Navigate to the project directory
```bash
cd restaurant-analytics-agent
```

### 4. Deploy to Vercel
```bash
vercel
```

Follow the prompts:
- Set up and deploy? **Yes**
- Which scope? (Select your account/team)
- Link to existing project? **No** (for first deployment)
- Project name? (Press Enter for default or enter a custom name)
- Directory? (Press Enter for current directory)

### 5. Set Environment Variables

After deployment, set your environment variables in the Vercel dashboard:

1. Go to your project on [vercel.com](https://vercel.com)
2. Navigate to **Settings** → **Environment Variables**
3. Add the following variables:

#### Required Environment Variables:

```bash
# Database Configuration
SUPABASE_DB_URL=postgresql://postgres:PASSWORD@db.PROJECT.supabase.co:5432/postgres
# OR use separate variables:
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_PASSWORD=your_password

# LLM Provider (choose one)
LLM_PROVIDER=nvidia  # or "grok"

# NVIDIA API (if using NVIDIA)
NVIDIA_API_KEY=your_nvidia_api_key
NVIDIA_MODEL=ai-nemotron-3-nano-30b-a3b

# Grok/XAI API (if using Grok)
GROK_API_KEY=your_grok_api_key
GROK_MODEL=grok-2
GROK_BASE_URL=https://api.x.ai/v1

# JWT Authentication (optional)
JWT_SECRET_KEY=your_secret_key
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Optional Settings
LOG_LEVEL=INFO
MAX_QUERY_TIMEOUT=30
MAX_RETRIES=2
DB_POOL_MIN_SIZE=5
DB_POOL_MAX_SIZE=20
```

### 6. Redeploy After Setting Environment Variables

After setting environment variables, redeploy:
```bash
vercel --prod
```

Or trigger a redeploy from the Vercel dashboard.

## Project Structure

```
restaurant-analytics-agent/
├── api/
│   └── index.py          # Vercel serverless function entry point
├── backend/               # Your FastAPI application
│   ├── main.py
│   ├── agents/
│   ├── config/
│   └── ...
├── vercel.json            # Vercel configuration
├── requirements.txt       # Python dependencies
└── .vercelignore          # Files to ignore during deployment
```

## Configuration Details

### vercel.json

The `vercel.json` file configures:
- **Python version**: 3.11
- **Function timeout**: 60 seconds (max for Pro plan)
- **Memory**: 3008 MB (max for Pro plan)
- **Routes**: All routes (`/*`) are handled by `api/index.py`

### Function Limits

- **Free Plan**: 10 seconds timeout, 1024 MB memory
- **Pro Plan**: 60 seconds timeout, 3008 MB memory
- **Enterprise**: Custom limits

For long-running queries, consider upgrading to Pro plan or using background jobs.

## Troubleshooting

### Issue: Function timeout
**Solution**: 
- Upgrade to Pro plan (60s timeout)
- Optimize query performance
- Consider breaking long operations into smaller chunks

### Issue: Database connection errors
**Solution**:
- Verify `SUPABASE_DB_URL` is correct
- Check if Supabase allows connections from Vercel IPs
- Ensure database pool settings are appropriate

### Issue: Import errors
**Solution**:
- Verify all dependencies are in `requirements.txt`
- Check that `api/index.py` correctly adds backend to Python path
- Review Vercel build logs for missing dependencies

### Issue: CORS errors
**Solution**:
- Update CORS settings in `backend/main.py` to allow your frontend domain
- Add your frontend URL to `allow_origins` in CORS middleware

## Monitoring

- View logs in Vercel dashboard: **Deployments** → Select deployment → **Functions** tab
- Monitor function performance: **Analytics** tab
- Set up alerts: **Settings** → **Monitoring**

## Production Checklist

- [ ] All environment variables set in Vercel dashboard
- [ ] CORS configured for production frontend domain
- [ ] Database connection pool size optimized
- [ ] Error logging configured
- [ ] Monitoring/alerts set up
- [ ] API rate limiting considered (if needed)
- [ ] Security headers configured (if needed)

## Additional Resources

- [Vercel Python Documentation](https://vercel.com/docs/functions/serverless-functions/runtimes/python)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [Vercel CLI Reference](https://vercel.com/docs/cli)

