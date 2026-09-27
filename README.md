# Système de gestion des objets trouvés

Projet réalisé dans le cadre d'un mémoire de fin de cycle Master 2 — Génie Logiciel,
Institut Africain de Technologie (IAT), Niamey, Niger.

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

## Documentation du projet

Chaque étape de développement est accompagnée d'un document expliquant le code écrit,
disponible en parallèle de ce dépôt.
