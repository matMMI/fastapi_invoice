#!/bin/bash

# Deployment script for Devis Generator API
# Usage: ./deploy.sh ["commit message"]
# If commit message is provided, Vercel deployment is automatic.
# If not, interactive mode is used.

set -e

echo "🚀 Déploiement de l'API Devis Generator"
echo "========================================"

COMMIT_MSG="$1"
INTERACTIVE=true

if [[ -n "$COMMIT_MSG" ]]; then
    INTERACTIVE=false
fi

# 1. GIT OPERATIONS
if [[ -z $(git status -s) ]]; then
    echo "ℹ️  Aucun changement à commiter"
else
    echo "📝 Ajout des fichiers modifiés..."
    git add .
    
    if [[ "$INTERACTIVE" == "true" ]]; then
        echo ""
        read -p "💬 Message de commit (Enter pour défaut): " input_msg
        if [[ -n "$input_msg" ]]; then
            COMMIT_MSG="$input_msg"
        fi
    fi
    
    if [[ -z "$COMMIT_MSG" ]]; then
        COMMIT_MSG="Update API - $(date +%Y-%m-%d\ %H:%M:%S)"
    fi
    
    echo "📦 Commit: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
fi

# 2. PUSH
if git remote -v | grep -q origin; then
    echo "⬆️  Push vers le dépôt distant..."
    current_branch=$(git branch --show-current)
    git push origin "$current_branch"
    echo "✅ Push réussi"
else
    echo "⚠️  Pas de remote 'origin'. Changements locaux uniquement."
fi

# 3. VERCEL DEPLOYMENT
echo ""
echo "🎯 Déploiement Vercel"
echo "===================="

if ! command -v vercel &> /dev/null; then
    echo "⚠️  Vercel CLI non installé (npm i -g vercel)"
else
    SHOULD_DEPLOY=false
    
    SHOULD_DEPLOY=true
    
    if [[ "$SHOULD_DEPLOY" == "true" ]]; then
        echo "🚀 Déploiement en production..."
        vercel --prod
    else
        echo "ℹ️  Déploiement skippé (sera géré par Git Push si connecté)."
    fi
fi

echo ""
echo "✨ Terminé!"
