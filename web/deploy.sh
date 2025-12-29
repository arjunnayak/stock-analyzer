#!/bin/bash

# Deploy Material Changes Web App to Cloudflare Pages
# Usage: ./deploy.sh [production|preview]

set -e

ENVIRONMENT=${1:-preview}

echo "======================================================"
echo "Material Changes - Cloudflare Pages Deployment"
echo "======================================================"
echo ""
echo "Environment: $ENVIRONMENT"
echo ""

# Check if wrangler is installed
if ! command -v wrangler &> /dev/null; then
    echo "Error: wrangler CLI is not installed"
    echo "Install with: npm install -g wrangler"
    exit 1
fi

# Check if logged in to Cloudflare
if ! wrangler whoami &> /dev/null; then
    echo "Not logged in to Cloudflare. Running login..."
    wrangler login
fi

echo "Building application..."
npm run pages:build

if [ $? -ne 0 ]; then
    echo "Build failed!"
    exit 1
fi

echo ""
echo "Build successful!"
echo ""

if [ "$ENVIRONMENT" = "production" ]; then
    echo "Deploying to production..."
    wrangler pages deploy .vercel/output/static --project-name=stock-analyzer --branch=main
else
    echo "Deploying preview..."
    wrangler pages deploy .vercel/output/static --project-name=stock-analyzer --branch=preview
fi

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================================"
    echo "Deployment successful!"
    echo "======================================================"
    echo ""
    echo "Your app should be available at:"
    echo "https://stock-analyzer.pages.dev"
    echo ""
else
    echo ""
    echo "Deployment failed!"
    exit 1
fi
