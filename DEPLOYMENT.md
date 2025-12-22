# Deployment Instructions for Devis Generator API

## Summary of Changes

To fix the `FUNCTION_INVOCATION_FAILED` error, the following changes were made to the API codebase:

### 1. Created `vercel.json` Configuration

- Configures Vercel to use Python runtime for serverless functions
- Routes all requests to `index.py` entry point
- Sets appropriate Lambda size limits

### 2. Updated Import Paths

All files were updated to remove the `api.` prefix from imports since the working directory in Vercel's serverless environment is already inside the API directory:

- ✅ `main.py` - Updated core imports
- ✅ `index.py` - Simplified to directly import from `main`
- ✅ `db/session.py` - Updated config import and optimized pooling
- ✅ `routers/clients.py` & `routers/quotes.py` - Updated all imports
- ✅ `core/security.py` - Updated imports
- ✅ `models/__init__.py`, `models/quote.py` - Updated internal imports
- ✅ `schemas/__init__.py`, `schemas/quote.py` - Updated imports
- ✅ `services/pdf_generator.py` - Updated model import

### 3. Optimized Database Connection Pooling

Updated `db/session.py` to use serverless-optimized settings:

- `pool_size=1` (minimal pool since each Lambda has its own engine)
- `pool_recycle=3600` (recycle connections after 1 hour)
- Added connection timeout (10s)
- Set timezone to UTC

## Required Environment Variables

⚠️ **CRITICAL**: You must configure the following environment variables in Vercel before the deployment will work:

1. **DATABASE_URL** - Already in `vercel.env`
2. **CORS_ORIGINS** - Already in `vercel.env`
3. **ENVIRONMENT** - Already in `vercel.env`
4. **BETTER_AUTH_SECRET** - ⚠️ **MISSING** - You must add this!

### How to Set Environment Variables in Vercel

#### Option 1: Via Vercel Dashboard (Recommended)

1. Go to https://vercel.com/dashboard
2. Select your `devis-generator-api` project
3. Navigate to **Settings** → **Environment Variables**
4. Add the following variables:
   - `DATABASE_URL`: Copy from `vercel.env`
   - `CORS_ORIGINS`: Copy from `vercel.env`
   - `ENVIRONMENT`: `production`
   - `BETTER_AUTH_SECRET`: Generate with `openssl rand -base64 32`
5. Make sure to select "Production" environment for each variable

#### Option 2: Via Vercel CLI

```bash
cd /Users/mthtgi/Desktop/vercel/devis_fullstack/devis_generator_api

# Install Vercel CLI if needed
npm i -g vercel

# Login to Vercel
vercel login

# Add environment variables
vercel env add BETTER_AUTH_SECRET production
# (paste the generated secret when prompted)

# You can generate a secret with:
openssl rand -base64 32
```

## Deployment Steps

### Deploy to Vercel

1. **Commit your changes** (if using Git):

```bash
cd /Users/mthtgi/Desktop/vercel/devis_fullstack/devis_generator_api
git add vercel.json index.py main.py db/ routers/ core/ models/ schemas/ services/
git commit -m "Fix serverless deployment configuration"
git push
```

2. **Deploy via Vercel Dashboard:**

   - Go to your Vercel dashboard
   - The deployment should trigger automatically if connected to Git
   - Or use the "Deploy" button for manual deployment

3. **Or deploy via Vercel CLI:**

```bash
cd /Users/mthtgi/Desktop/vercel/devis_fullstack/devis_generator_api
vercel --prod
```

### Verify the Deployment

After deployment completes, test these endpoints:

1. **Health check**: `https://devisgeneratorapi.vercel.app/health`

   - Should return: `{"status": "healthy"}`

2. **Root endpoint**: `https://devisgeneratorapi.vercel.app/`

   - Should return: `{"message": "Hello World", "environment": "production"}`

3. **API documentation**: `https://devisgeneratorapi.vercel.app/api/docs`
   - Should display the Swagger UI interface

## Troubleshooting

### If the deployment still fails:

1. **Check Vercel build logs**:

   - Go to your project in Vercel Dashboard
   - Click on the failed deployment
   - Review the "Build Logs" and "Function Logs"

2. **Verify environment variables are set**:

   - Go to Settings → Environment Variables
   - Make sure all 4 required variables are present
   - Check for typos in variable names

3. **Check for Python dependency issues**:
   - Make sure `requirements.txt` is in the root of the API directory
   - Verify all dependencies have compatible versions

### Common Issues:

- **"Module not found" errors**: Make sure all `api.` prefixes were removed from imports
- **Database connection errors**: Verify `DATABASE_URL` is correct and the database is accessible
- **Authentication errors**: Ensure `BETTER_AUTH_SECRET` is set correctly
- **CORS errors**: Check that your frontend URL is in `CORS_ORIGINS`

## Next Steps

Once the deployment is successful:

1. Test authenticated endpoints from your frontend
2. Verify client and quote CRUD operations work correctly
3. Test PDF generation functionality
4. Monitor error logs for any runtime issues
