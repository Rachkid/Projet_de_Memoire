"""
Applique automatiquement les migrations Alembic en attente au démarrage.

Ordre au démarrage (voir main.py) :
  1. create_all crée les tables qui n'existent pas (base neuve) ;
  2. ce module met à niveau les tables qui existent déjà (base d'une étape précédente).
Ainsi un client qui met à jour l'application n'a rien à lancer à la main, et ses
données sont conservées.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config


def appliquer_migrations() -> None:
    configuration = Config()  # configuration construite en code : pas besoin de fichier alembic.ini
    configuration.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    command.upgrade(configuration, "head")
