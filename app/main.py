"""
Point d'entrée de l'application : assemble la base de données, les modèles
et les routers écrits dans les étapes précédentes en une seule application
FastAPI exécutable.
"""

from fastapi import FastAPI

from app.database import Base, engine
from app.models import (  # noqa: F401 — l'import garantit que tous les modèles
    Organisation,          # sont enregistrés auprès de SQLAlchemy avant la
    Utilisateur,           # création des tables ci-dessous.
    Usager,
    Objet,
    Restitution,
    SignalementPerte,
)
from app.routers import objets, organisations, usagers, utilisateurs

# Crée les tables dans la base de données si elles n'existent pas encore.
# Cette approche simple convient à cette étape de développement ; une
# gestion plus rigoureuse des évolutions futures du schéma (ajout d'une
# colonne, par exemple, sans perdre les données déjà présentes chez un
# client) sera mise en place avec Alembic lors d'une prochaine étape.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Système de gestion des objets trouvés",
    description=(
        "API du projet de mémoire de fin de cycle M2 Génie Logiciel — "
        "Institut Africain de Technologie (IAT), Niamey, Niger."
    ),
    version="0.1.0",
)

# Chaque router déclare lui-même son préfixe d'URL (ex. : /objets) ;
# il suffit donc de l'enregistrer ici pour que ses routes deviennent actives.
app.include_router(organisations.router)
app.include_router(utilisateurs.router)
app.include_router(usagers.router)
app.include_router(objets.router)


@app.get("/", tags=["Racine"])
def accueil():
    """Simple point de contrôle confirmant que l'API est en ligne."""
    return {
        "message": "API Système de gestion des objets trouvés.",
        "documentation_interactive": "/docs",
    }
