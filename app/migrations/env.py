"""
Environnement Alembic : indique à Alembic où est la base de données et quels sont
les modèles. Alembic sert à FAIRE ÉVOLUER le schéma (ajouter une colonne, par
exemple) sans perdre les données déjà présentes chez un client : chaque évolution
est écrite une fois dans un fichier de « migration » rangé dans versions/.
"""

from alembic import context

from app.database import Base, engine
from app.models import (  # noqa: F401 — l'import enregistre les modèles dans Base.metadata
    Objet,
    Organisation,
    Restitution,
    SignalementPerte,
    Usager,
    Utilisateur,
)

# Décrit les tables attendues ; sert à `alembic revision --autogenerate` pour proposer les migrations.
target_metadata = Base.metadata


def run_migrations_online() -> None:
    # On réutilise le moteur de l'application : mêmes identifiants, une seule configuration.
    with engine.connect() as connexion:
        context.configure(connection=connexion, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
