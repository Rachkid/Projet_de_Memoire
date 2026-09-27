"""
Ce fichier centralise toute la configuration de l'application (identifiants
de la base de données, clé secrète, etc.), lue depuis les variables
d'environnement définies dans le fichier .env.

Centraliser cette lecture ici, plutôt que d'appeler os.environ un peu partout
dans le code, permet de savoir en un seul endroit quelles informations de
configuration l'application attend, et de les valider automatiquement.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Identifiants de la base de données (repris du fichier .env)
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url: str

    # Clé secrète utilisée pour signer les jetons de connexion des agents
    secret_key: str

    # Paramètres de l'algorithme de signature et de la durée de vie du jeton
    # (utilisés à partir de l'étape d'authentification des agents)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 8  # 8 heures : une journée de travail

    # Indique à Pydantic de lire les valeurs manquantes depuis le fichier .env
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """
    Construit l'objet Settings une seule fois puis le garde en mémoire
    (grâce à @lru_cache), plutôt que de relire le fichier .env à chaque fois
    que la configuration est utilisée ailleurs dans le code.
    """
    return Settings()


# Instance unique de configuration, importée directement par les autres fichiers
# du projet (ex. : from app.config import settings)
settings = get_settings()
