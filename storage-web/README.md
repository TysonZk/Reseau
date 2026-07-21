# 💾 storage-web

Dashboard web léger pour visualiser le stockage d'un serveur : systèmes de
fichiers, disques physiques, périphériques loop et usage Docker. Ecrit en **Python / Flask** et packagée avec **Docker**.

![port](https://img.shields.io/badge/port-8888-6366f1) ![python](https://img.shields.io/badge/python-3.12-blue) ![flask](https://img.shields.io/badge/flask-3.1-black)

## Fonctionnalités

- 📊 **Systèmes de fichiers** — barres de progression colorées (vert / ambre / rouge)
- 🚨 **Alertes** automatiques dès qu'un montage dépasse **85 %**
- 💽 **Disques physiques** (modèle, taille, type) via `lsblk`
- 🐳 **Docker** — images, conteneurs, volumes, cache (`docker system df`)
- 🔁 **Périphériques loop**
- 🔔 **Alertes par webhook** — notification Discord / Slack / JSON quand un montage
  franchit le seuil, et retour à la normale (avec bouton de test dans l'UI)
- 🔄 Auto-actualisation toutes les 15 s, interface sombre et responsive

## Démarrage rapide (Docker)

```bash
docker compose up -d --build
```

Puis ouvrir **http://localhost:8888**

> Le conteneur tourne en `privileged` + `pid: host` et utilise `nsenter` pour
> lire les informations de **l'hôte** (et non celles du conteneur). Le socket
> Docker est monté en lecture seule pour la section Docker.

## Développement local (sans Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main            # http://localhost:8888
```

En local, les commandes s'exécutent directement (pas de `nsenter`).

## Configuration

| Variable               | Défaut | Description                                                        |
| ---------------------- | ------ | ----------------------------------------------------------------- |
| `PORT`                 | `8888` | Port d'écoute (mode dev `python -m app.main`)                     |
| `HOST_NSENTER`         | —      | `1` pour exécuter les commandes dans les namespaces de l'hôte     |
| `ALERT_WEBHOOK_URL`    | —      | URL du webhook d'alerte. Vide = alertes désactivées.              |
| `ALERT_THRESHOLD`      | `85`   | Seuil d'alerte, en % d'utilisation.                               |
| `ALERT_INTERVAL`       | `300`  | Fréquence de vérification, en secondes.                           |
| `ALERT_WEBHOOK_FORMAT` | `auto` | `auto` \| `discord` \| `slack` \| `json`.                         |

## Alertes par webhook

Copier `.env.example` en `.env` et renseigner l'URL du webhook :

```bash
cp .env.example .env
# éditer .env → ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
docker compose up -d
```

Une notification est envoyée quand un montage **dépasse** le seuil, puis une
autre quand il **repasse** en dessous (pas de spam : envoi uniquement sur
changement d'état). Le format est détecté automatiquement depuis l'URL
(`discord` / `slack`), sinon un JSON générique est posté :

```json
{
  "event": "alert",
  "hostname": "srv-01",
  "filesystem": { "mount": "/mnt/data", "usePct": 91, "avail": "1.1T", "size": "7.8T" },
  "message": "**srv-01** — le montage `/mnt/data` est à **91%** (1.1T restant sur 7.8T)."
}
```

Bouton **« Tester le webhook »** disponible dans l'interface, ou :

```bash
curl -X POST http://localhost:8888/api/test-webhook
```

## API

| Route                    | Description                          |
| ------------------------ | ------------------------------------ |
| `GET /`                  | Interface web                        |
| `GET /api/storage`       | Données de stockage au format JSON   |
| `GET /api/config`        | Config des alertes (seuil, webhook…) |
| `POST /api/test-webhook` | Envoie une notification de test      |
| `GET /healthz`           | Health check                         |

## Structure

```
storage-web/
├── app/
│   ├── main.py            # Application Flask (routes)
│   ├── collectors.py      # Collecte df / lsblk / docker
│   ├── alerts.py          # Surveillance + alertes par webhook
│   ├── templates/index.html
│   └── static/            # style.css, app.js
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

## Licence

MIT
