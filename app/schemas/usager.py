"""
Schémas Pydantic pour la ressource Usager (personnes extérieures sans compte).
"""

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.services.telephone import normaliser_telephone


class UsagerBase(BaseModel):
    telephone: str
    nom: Optional[str] = None


class UsagerCreate(UsagerBase):
    @field_validator("telephone")
    @classmethod
    def telephone_valide(cls, valeur: str) -> str:
        # Étape 16 : le serveur applique lui-même la règle de la page (8 chiffres du Niger ou numéro étranger en +).
        numero = normaliser_telephone(valeur)
        if numero is None:
            raise ValueError("Numéro de téléphone invalide : 8 chiffres (ex. 96 12 34 56) ou numéro étranger commençant par +.")
        return numero


class UsagerRead(UsagerBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
