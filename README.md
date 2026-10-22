# Retrova — Système de gestion des objets perdus

Retrova (de « retrouver » : retrouver l'objet pour le rendre à son propriétaire) est une plateforme de gestion des objets perdus et trouvés pour les établissements d'enseignement et les compagnies de transport. Projet réalisé dans le cadre d'un
mémoire de fin de cycle Master 2 — Génie Logiciel, Institut Africain de
Technologie (IAT), Niamey, Niger.

## Structure du projet

```
objets_trouves/
├── app/
│   ├── main.py           # Point d'entrée de l'application FastAPI
│   ├── database.py       # Connexion et session à la base de données
│   ├── config.py         # Lecture des variables d'environnement
│   ├── models/           # Tables de la base de données (SQLAlchemy)
│   ├── schemas/          # Formats de données validés en entrée/sortie de l'API (Pydantic)
│   ├── routers/          # Points d'accès de l'API, regroupés par ressource
│   ├── services/         # Logique réutilisable (photos, habillage, couleurs, rapprochement...)
│   ├── migrations/       # Évolutions du schéma de la base (Alembic)
│   ├── scripts/          # Outils en ligne de commande (super-administrateur, habillage de démonstration)
│   ├── assets/demo/      # Logos et photos de démonstration (IAT, Rimbo, STM, Amana, SONITRAV)
│   └── static/           # Pages HTML/CSS/JS (interface agent, écran, portail)
├── tests/                # Tests automatisés
├── requirements.txt      # Dépendances Python du projet
├── .env.example          # Modèle de fichier de configuration
├── Dockerfile            # Image de l'application
└── docker-compose.yml    # Orchestration application + base de données
```

## Démarrage (développement local avec Docker)

1. Copier `.env.example` vers `.env` et adapter les valeurs.
2. Lancer : `docker compose up --build`
3. L'API est accessible sur http://localhost:8000
4. La documentation interactive générée automatiquement par FastAPI est accessible sur http://localhost:8000/docs

## Habillage des organisations (Étape 10)

Chaque organisation a son identité visuelle : identifiant d'adresse (`iat`), logo, photo de fond et
couleurs. Pour appliquer l'habillage de démonstration à IAT, Rimbo, STM, Amana et SONITRAV :

```
docker compose exec api python -m app.scripts.habillage_demo
```

## Portail public (Étape 11)

Chaque organisation a une page publique à son identifiant court : `http://localhost:8000/iat`,
`/rimbo`, `/stm`, `/amana`, `/sonitrav`, `/nizar`, `/ema`, `/salim`. Un usager sans compte y déclare un objet perdu (le système cherche aussitôt
une correspondance) et, si l'organisation a activé la consultation à distance, voit les objets trouvés.
La page est conçue d'abord pour un téléphone et s'habille des couleurs, du logo et de la photo de
l'organisation. Fichiers : `app/static/portail/` ; routes : `app/routers/portail.py`.

## Interface des agents (Étape 12)

Chaque organisation a aussi son espace de travail à `/{identifiant}/agent` (par exemple
`http://localhost:8000/iat/agent`) : connexion, liste des objets, enregistrement d'un objet avec photo,
fiche avec code QR à imprimer, remise à son propriétaire (contrôle du détail secret, pièce d'identité),
déclarations de perte et changement de mot de passe. Les droits d'enregistrement et de restitution
sont vérifiés par le serveur ; la page ne fait que masquer ce que la personne ne peut pas faire.
Fichiers : `app/static/agent/` ; routes ajoutées : `GET /objets/{id}/signalements` et `GET /{identifiant}/agent`.
`GET /objets/` et `GET /objets/{id}` sont désormais réservées au personnel connecté de l'organisation.

## Écran d'affichage du hall (Étape 13)

`http://localhost:8000/iat/affichage` : une page plein écran à mettre sur une télévision à l'accueil.
Elle montre les objets trouvés (6 à la fois, en défilement s'il y en a plus), l'heure, et un code QR pour
déclarer une perte depuis son téléphone. Elle se met à jour toute seule chaque minute et n'expose que
ce que le portail public expose déjà. Touche F : plein écran. Fichiers : `app/static/affichage/` ;
route ajoutée : `GET /portail/{identifiant}/qrcode`. Une fois le site en ligne, renseigner
`ADRESSE_PUBLIQUE` dans `.env` (voir `.env.example`) pour que le code QR pointe vers la bonne adresse.

Les évolutions de la base sont gérées par Alembic et appliquées automatiquement au démarrage :
mettre l'application à jour ne fait perdre aucune donnée.

## Documentation du projet

Chaque étape de développement est accompagnée d'un document expliquant le code écrit,
disponible en parallèle de ce dépôt.
