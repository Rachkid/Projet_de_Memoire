"""Schémas Pydantic pour l'authentification."""

from pydantic import BaseModel


class Jeton(BaseModel):
    """Réponse à une connexion réussie (format standard OAuth2)."""

    access_token: str
    token_type: str = "bearer"
    # Étape 16 : vrai si le mot de passe est provisoire (la page doit alors demander d'en choisir un).
    doit_changer_mot_de_passe: bool = False
