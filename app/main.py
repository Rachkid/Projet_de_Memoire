"""
Point d'entrée de l'application : assemble la base de données, les modèles
et les routers écrits dans les étapes précédentes en une seule application
FastAPI exécutable.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.models import (  # noqa: F401 — l'import garantit que tous les modèles
    Organisation,          # sont enregistrés auprès de SQLAlchemy avant la
    Utilisateur,           # création des tables ci-dessous.
    Usager,
    Objet,
    Restitution,
    SignalementPerte,
)
from app.routers import auth, objets, organisations, photos, restitutions, signalements, usagers, utilisateurs

# Crée les tables dans la base de données si elles n'existent pas encore.
# Cette approche simple convient à cette étape de développement ; une
# gestion plus rigoureuse des évolutions futures du schéma (ajout d'une
# colonne, par exemple, sans perdre les données déjà présentes chez un
# client) sera mise en place avec Alembic lors d'une prochaine étape.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Rendia — Système de gestion des objets perdus",
    description=(
        "API du projet de mémoire de fin de cycle M2 Génie Logiciel — "
        "Institut Africain de Technologie (IAT), Niamey, Niger."
    ),
    version="0.3.0",
)

# Chaque router déclare lui-même son préfixe d'URL (ex. : /objets) ;
# il suffit donc de l'enregistrer ici pour que ses routes deviennent actives.
app.include_router(auth.router)
app.include_router(organisations.router)
app.include_router(utilisateurs.router)
app.include_router(usagers.router)
app.include_router(objets.router)
app.include_router(signalements.router)
app.include_router(restitutions.router)
app.include_router(photos.router)

# Les photos d'OBJETS sont publiques : on expose leur dossier tel quel. Le
# dossier des photos de propriétaires n'est volontairement PAS exposé ici.
photos.DOSSIER_OBJETS.mkdir(parents=True, exist_ok=True)
app.mount("/fichiers/objets", StaticFiles(directory=photos.DOSSIER_OBJETS), name="photos_objets")


@app.get("/", tags=["Racine"])
def accueil():
    """Simple point de contrôle confirmant que l'API est en ligne."""
    return {
        "message": "API Rendia — Système de gestion des objets perdus.",
        "documentation_interactive": "/docs",
    }
