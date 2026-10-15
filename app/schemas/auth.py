"""Schémas Pydantic pour l'authentification."""

from pydantic import BaseModel


class Jeton(BaseModel):
    """Réponse à une connexion réussie (format standard OAuth2)."""

    access_token: str
    token_type: str = "bearer"
