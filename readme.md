# Devis Generator API

## Variables d'environnement

### Base de données

- **DATABASE_URL** : Chaîne de connexion PostgreSQL avec SSL
  - Format : `postgresql://user:password@host/database?sslmode=require&channel_binding=require`

### Authentification

- **BETTER_AUTH_SECRET** : Clé secrète utilisée par Better Auth pour signer les sessions et tokens. Doit faire au moins 32 caractères.

  ```bash
  # Avec openssl
  openssl rand -base64 32

  # Avec Node.js
  node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"
  ```

### Configuration applicative

- **ENVIRONMENT** : Environnement de déploiement (`production`, `staging`, `development`)
- **CORS_ORIGINS** : Liste des origines CORS autorisées, séparées par des virgules
  - Exemple : `https://mondomaine.com,http://localhost:3000`

### Optionnel

- **BLOB_READ_WRITE_TOKEN** : Token pour Vercel Blob (stockage PDF)
- **DEBUG** : Active le mode debug et les logs SQL (déconseillé en production)

---

## Développement local

Copier `vercel.env` vers `.env` et ajouter le secret manquant :

```bash
cp vercel.env .env
echo "BETTER_AUTH_SECRET=$(openssl rand -base64 32)" >> .env
```

---

## Déploiement Vercel

1. Aller dans le projet sur le Dashboard Vercel
2. Naviguer vers Settings > Environment Variables
3. Ajouter chaque variable avec sa valeur
4. Sélectionner l'environnement approprié (Production, Preview, Development)
