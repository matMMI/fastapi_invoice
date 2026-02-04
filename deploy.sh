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

# 0. RUN TESTS
echo "🧪 Exécution des tests unitaires..."
./venv/bin/python -m pytest tests/ -v --tb=short
if [[ $? -ne 0 ]]; then
    echo "❌ Tests échoués! Déploiement annulé."
    exit 1
fi
echo "✅ Tous les tests passent!"
echo ""

# 1. GIT OPERATIONS
if [[ -z $(git status -s) ]]; then
    echo "ℹ️  Aucun changement à commiter"
else
    echo "📝 Ajout des fichiers modifiés..."
    git add -u  # Only stage tracked files, never new untracked files
    
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

# 3. MIGRATIONS EN PRODUCTION
echo ""
echo "🔄 Migrations de la base de données"
echo "===================================="

TEMP_ENV=$(mktemp)
vercel env pull "$TEMP_ENV" --environment production --yes 2>/dev/null

PROD_DB_URL=$(grep "^DATABASE_URL=" "$TEMP_ENV" | sed 's/^DATABASE_URL=//' | sed 's/^"//' | sed 's/"$//')
rm -f "$TEMP_ENV"

if [[ -n "$PROD_DB_URL" ]]; then
    echo "🔄 Exécution des migrations en production..."
    DATABASE_URL="$PROD_DB_URL" ./venv/bin/python run_migrations.py
    if [[ $? -ne 0 ]]; then
        echo "❌ Migrations échouées! Déploiement annulé."
        exit 1
    fi
    echo "✅ Migrations exécutées avec succès!"
else
    echo "⚠️  DATABASE_URL production non trouvée via Vercel CLI."
    echo "   Migrations non exécutées. Vérifiez vos variables d'environnement Vercel."
fi

# 4. VERCEL DEPLOYMENT
echo ""
echo "🎯 Déploiement Vercel"
echo "===================="

if ! command -v vercel &> /dev/null; then
    echo "⚠️  Vercel CLI non installé (npm i -g vercel)"
else
    echo "🚀 Déploiement en production..."
    vercel --prod
fi

echo ""
echo "✨ Terminé!"
