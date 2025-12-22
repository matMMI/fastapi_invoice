#!/bin/bash

# Deployment script for Devis Generator API
# This script commits changes and deploys to Vercel

set -e  # Exit on error

echo "🚀 Déploiement de l'API Devis Generator"
echo "========================================"

# Check if there are changes to commit
if [[ -z $(git status -s) ]]; then
    echo "ℹ️  Aucun changement à commiter"
else
    echo "📝 Ajout des fichiers modifiés..."
    git add .
    
    # Ask for commit message
    echo ""
    read -p "💬 Message de commit (appuyez sur Entrée pour le message par défaut): " commit_message
    
    if [[ -z "$commit_message" ]]; then
        commit_message="Update API - $(date +%Y-%m-%d\ %H:%M:%S)"
    fi
    
    echo "📦 Commit des changements..."
    git commit -m "$commit_message"
fi

# Check if we're in a git repository with a remote
if git remote -v | grep -q origin; then
    echo "⬆️  Push vers le dépôt distant..."
    
    # Get current branch
    current_branch=$(git branch --show-current)
    
    git push origin "$current_branch"
    echo "✅ Push réussi vers origin/$current_branch"
else
    echo "⚠️  Aucun remote 'origin' configuré. Les changements sont commitées localement seulement."
fi

echo ""
echo "🎯 Déploiement Vercel"
echo "===================="

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null; then
    echo "⚠️  Vercel CLI n'est pas installé"
    echo "   Installer avec: npm i -g vercel"
    echo ""
    echo "   Le déploiement sera automatiquement déclenché par le push Git si"
    echo "   votre projet est connecté à Vercel."
else
    # Ask if user wants to deploy with Vercel CLI
    read -p "❓ Voulez-vous déployer avec Vercel CLI maintenant? (o/N): " deploy_now
    
    if [[ "$deploy_now" =~ ^[Oo]$ ]]; then
        echo "🚀 Déploiement en production..."
        vercel --prod
    else
        echo "ℹ️  Le déploiement sera automatiquement déclenché par le push Git."
    fi
fi

echo ""
echo "✨ Terminé!"
echo ""
echo "📍 Vérifiez le déploiement sur:"
echo "   https://vercel.com/dashboard"
echo ""
echo "🔍 Testez les endpoints:"
echo "   - https://devisgeneratorapi.vercel.app/health"
echo "   - https://devisgeneratorapi.vercel.app/"
echo "   - https://devisgeneratorapi.vercel.app/api/docs"
