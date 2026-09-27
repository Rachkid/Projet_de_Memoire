"""
Ce fichier met en place la connexion à la base de données PostgreSQL et
fournit les outils dont le reste de l'application a besoin pour lire et
écrire des données : le moteur de connexion, la fabrique de sessions,
la classe de base des modèles, et une fonction de dépendance pour FastAPI.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# Le moteur (engine) est le point d'entrée unique vers la base de données :
# il sait comment s'y connecter, mais ne fait rien tant qu'on ne le lui demande pas.
# pool_pre_ping=True vérifie qu'une connexion est toujours valide avant de
# l'utiliser, ce qui évite des erreurs si la base a redémarré entre-temps.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# SessionLocal est une "fabrique" de sessions : chaque requête reçue par
# l'API en ouvrira une nouvelle instance pour dialoguer avec la base,
# puis la refermera une fois la réponse envoyée.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Toutes les classes de modèles du dossier models/ hériteront de cette
# classe Base : c'est ce qui permet à SQLAlchemy de savoir quelles tables
# existent et comment elles sont structurées.
Base = declarative_base()


def get_db():
    """
    Fonction de dépendance utilisée par FastAPI (via Depends(get_db) dans
    les routers) : elle ouvre une session de base de données, la met à
    disposition de la fonction qui traite la requête, puis garantit
    qu'elle est toujours refermée à la fin, même si une erreur survient.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
