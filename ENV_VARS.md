# Devis Generator API - Environment Variables

This file documents the required environment variables for deploying the API to Vercel.

## Required Environment Variables

### Database Configuration

- **DATABASE_URL**: PostgreSQL connection string with SSL mode
  - Format: `postgresql://username:password@host/database?sslmode=require&channel_binding=require`
  - Example provided in `vercel.env`

### Authentication

- **BETTER_AUTH_SECRET**: Secret key for Better Auth authentication system
  - **⚠️ REQUIRED**: This must be set before deployment
  - Generate with: `openssl rand -base64 32`
  - Keep this secret and never commit it to version control

### Application Configuration

- **ENVIRONMENT**: Deployment environment (e.g., "production", "staging", "development")
- **CORS_ORIGINS**: Comma-separated list of allowed CORS origins
  - Example: `https://yourdomain.com,http://localhost:3000`

### Optional Variables

- **BLOB_READ_WRITE_TOKEN**: Token for Vercel Blob storage (optional, for PDF storage)
- **DEBUG**: Enable debug mode and SQL query logging (not recommended for production)

## Setting Environment Variables in Vercel

1. Go to your project in Vercel Dashboard
2. Navigate to Settings → Environment Variables
3. Add each variable with its corresponding value
4. Make sure to set the appropriate environment (Production, Preview, Development)

## Local Development

For local development, copy `vercel.env` to `.env` and add the missing `BETTER_AUTH_SECRET`:

```bash
cp vercel.env .env
echo "BETTER_AUTH_SECRET=$(openssl rand -base64 32)" >> .env
```
