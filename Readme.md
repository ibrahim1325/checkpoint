# 🎯 Checkpoint

> Une app de planning partagé entre amis — avec messagerie intégrée, MFA et contrôle de confidentialité granulaire.

🌐 **Démo en ligne :** [checkpoint-uh9x.onrender.com](https://checkpoint-uh9x.onrender.com)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-336791?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

> ⏰ L'instance gratuite Render se met en veille après 15 min d'inactivité — le premier chargement peut prendre ~30 secondes.

---

## 💡 Le problème

Coordonner un plan avec 5 amis = 47 messages, 3 sondages, et personne ne se rappelle de la date finale. Snap, iMessage, Discord, Doodle — le plan se perd entre 50 conversations.

## 🎯 La solution

**Checkpoint** te permet de voir directement les disponibilités de tes amis (s'ils acceptent de les partager), de leur écrire dans la même interface, et de tout garder à un seul endroit.

---

## ✨ Fonctionnalités

- 🔐 **Authentification sécurisée** — email/mot de passe + 2FA par email, Google OAuth, réinitialisation de mot de passe avec tokens à expiration
- 📅 **Planning hebdomadaire** — remplis ton emploi du temps, marque tes plages comme libres, occupées ou tentatives
- 👁️ **Confidentialité granulaire** — choisis qui voit ton planning : personne, tous tes amis, ou une liste personnalisée
- 👥 **Système d'amis** — envoie, accepte ou refuse des demandes d'ami
- 💬 **Messagerie directe** — texte et pièces jointes (jusqu'à 2 Mo), modification et suppression de tes propres messages, indicateurs de lecture
- 🎨 **Thèmes personnalisables** — couleur principale, fond et encre configurables par l'utilisateur
- 🟢 **Statuts de présence** — en ligne, inactif, ne pas déranger, invisible

---

## 🛠️ Stack technique

| Couche | Technologie |
|---|---|
| Backend | Python · Flask · Gunicorn |
| Base de données | PostgreSQL (hébergée sur [Neon](https://neon.tech)) |
| Frontend | HTML · CSS · JavaScript · Jinja2 |
| Authentification | Authlib (OAuth Google) · Werkzeug security · Flask-Mail (MFA + reset) |
| Hébergement | [Render](https://render.com) |

---

## 🧠 Points techniques intéressants

Ce que j'ai le plus appris en construisant ce projet :

### 🔐 Authentification à deux facteurs from scratch
J'ai implémenté un flux MFA complet par email : codes hashés stockés en base, expiration de 10 minutes, usage unique, et mécanisme de renvoi — sans dépendre d'un fournisseur d'auth tiers.

### 🔒 Confidentialité granulaire du planning
Trois modes (`none`, `friends`, `custom`) avec permissions vérifiées côté serveur à chaque endpoint. La logique : être ami n'implique pas automatiquement de voir le planning — la confidentialité est *opt-in*, pas *opt-out*.

### 💬 Messagerie avec pièces jointes
Validation côté serveur pour la taille (limite 2 Mo) et le type de contenu. Noms de fichiers uniques générés par UUID pour éviter les collisions. Compteur de messages non lus injecté globalement via `context_processor` de Flask.

### 🌐 Intégration OAuth
Connexion Google avec import de l'avatar (téléchargé et stocké en base64 pour éviter le hotlinking) et logique de fusion de comptes (email existant → réutilisation du compte, sinon génération automatique d'un username unique).

---

## 🚀 Installation locale

### Prérequis

- Python 3.11+
- Un compte gratuit sur [Neon](https://neon.tech) pour la base PostgreSQL
- Un compte Gmail avec un [App Password](https://support.google.com/accounts/answer/185833) (pour l'envoi d'emails)
- Des credentials Google OAuth ([Google Cloud Console](https://console.cloud.google.com/apis/credentials))

### Étapes

#### 1. Cloner le dépôt

```bash
git clone https://github.com/ibrahim1325/checkpoint.git
cd checkpoint
```

#### 2. Installer les dépendances

```bash
pip install -r backend/requirements.txt
```

#### 3. Configurer les variables d'environnement

```bash
cd backend
cp .env.example .env
```

Édite le fichier `.env` avec tes propres credentials :

```env
SECRET_KEY=une_cle_secrete_aleatoire

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

FACEBOOK_CLIENT_ID=...
FACEBOOK_CLIENT_SECRET=...

MAIL_USERNAME=ton_email@gmail.com
MAIL_PASSWORD=ton_app_password_gmail

NEON_DB=postgresql://user:password@host/dbname?sslmode=require
```

> 💡 Pour `MAIL_PASSWORD`, utilise un App Password Gmail (pas ton mot de passe principal).
> 💡 Pour `NEON_DB`, crée un projet gratuit sur [neon.tech](https://neon.tech).

#### 4. Créer les tables dans la base de données

Exécute le script SQL suivant dans la console SQL de ton projet Neon :

```sql
-- Table des utilisateurs
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(20) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password TEXT,
    profile_pic TEXT,
    bio TEXT,
    theme VARCHAR(20) DEFAULT 'dark',
    primary_color VARCHAR(20) DEFAULT '#FFD400',
    bg_color VARCHAR(20) DEFAULT '#1a1a1a',
    ink_color VARCHAR(20) DEFAULT '#111111',
    status VARCHAR(20) DEFAULT 'online',
    mfa_enabled BOOLEAN DEFAULT FALSE
);

-- Table des amis
CREATE TABLE IF NOT EXISTS friends (
    user_name VARCHAR(20) NOT NULL,
    friend VARCHAR(20) NOT NULL,
    PRIMARY KEY (user_name, friend)
);

-- Table des demandes d'amis
CREATE TABLE IF NOT EXISTS friend_requests (
    id SERIAL PRIMARY KEY,
    from_user VARCHAR(20) NOT NULL,
    to_user VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (from_user, to_user)
);

-- Table des messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    from_user VARCHAR(20) NOT NULL,
    to_user VARCHAR(20) NOT NULL,
    content TEXT DEFAULT '',
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE,
    attachment_url TEXT,
    attachment_name TEXT,
    attachment_mime TEXT
);

-- Table du planning
CREATE TABLE IF NOT EXISTS planning (
    user_name VARCHAR(20) NOT NULL,
    cell_id VARCHAR(50) NOT NULL,
    content TEXT DEFAULT '',
    state VARCHAR(20) DEFAULT 'free',
    week DATE NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_name, cell_id, week)
);

-- Table des codes MFA
CREATE TABLE IF NOT EXISTS mfa_codes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table de confidentialité du planning
CREATE TABLE IF NOT EXISTS schedule_privacy (
    user_name VARCHAR(20) PRIMARY KEY,
    mode VARCHAR(20) DEFAULT 'friends'
);

-- Table des amis autorisés (mode custom)
CREATE TABLE IF NOT EXISTS schedule_privacy_custom (
    user_name VARCHAR(20) NOT NULL,
    friend VARCHAR(20) NOT NULL,
    PRIMARY KEY (user_name, friend)
);

-- Table de réinitialisation de mot de passe
CREATE TABLE IF NOT EXISTS password_resets (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    token VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 5. Lancer l'application

```bash
cd backend
python3 app.py
```

L'application sera accessible sur `http://localhost:5000`.

---

## 📁 Structure du projet

```
checkpoint/
├── backend/
│   ├── app.py              # Serveur Flask : routes, auth, logique métier
│   ├── requirements.txt    # Dépendances Python
│   ├── .env                # Variables d'environnement (ignoré par Git)
│   └── .env.example        # Exemple de configuration
├── frontend/
│   ├── templates/          # Pages HTML (Jinja2)
│   └── static/             # CSS, JavaScript, uploads
├── Procfile                # Config de déploiement Render
└── README.md
```

---

## 📸 Captures d'écran

### Authentification
![Page de connexion](docs/screenshots/Login.png)

### Planning hebdomadaire
![Schedule avec gestion de la confidentialité](docs/screenshots/planning.png)

### Système d'amis
![Liste d'amis et messagerie](docs/screenshots/Messagerie.png)
---

## 📝 Licence

MIT — libre d'utilisation, fork et apprentissage.

---

## 👤 Auteur

**Ibrahim Bérété** — Étudiant en informatique à l'UQAM
[GitHub](https://github.com/ibrahim1325)