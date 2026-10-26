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

    # Stockage des photos (étape 7). Dans Docker, ce dossier est relié à un
    # volume persistant : les photos survivent aux redémarrages du conteneur.
    upload_dir: str = "uploads"
    photo_max_octets: int = 5 * 1024 * 1024  # 5 Mo par photo reçue
    photo_max_cote: int = 1600  # la plus grande dimension est ramenée à 1600 px

    # Adresse publique du site (ex. https://objets.iat.ne), facultative. Elle sert à fabriquer le code QR
    # « déclarer une perte » de l'écran d'affichage. Si elle est vide, l'adresse utilisée par le
    # navigateur est reprise telle quelle (suffisant en essai local ; à renseigner une fois en ligne).
    adresse_publique: str = ""

    # Envoi de courriels (étape 15). Si smtp_host est vide, AUCUN courriel n'est envoyé : le message
    # est seulement écrit dans les journaux. En essai local, docker-compose démarre MailHog (smtp_host=mailhog,
    # port 1025) : les courriels y sont captés et lisibles sur http://localhost:8025, sans rien envoyer
    # dehors. En production : renseigner le serveur SMTP du client (voir .env.example).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_utilisateur: str = ""
    smtp_mot_de_passe: str = ""
    smtp_starttls: bool = False  # chiffrement STARTTLS (en général port 587)
    smtp_ssl: bool = False  # chiffrement SSL direct (en général port 465)
    courriel_expediteur: str = "Tsintuwa <ne-pas-repondre@tsintuwa.local>"

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
