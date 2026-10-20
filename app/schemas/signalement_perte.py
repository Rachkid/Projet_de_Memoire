"""
Schémas Pydantic pour la ressource SignalementPerte.
"""

import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatutSignalement


class SignalementPerteBase(BaseModel):
    categorie: str
    description: Optional[str] = None
    date_perte: Optional[date] = None
    lieu_approximatif: Optional[str] = None


class SignalementPerteCreate(SignalementPerteBase):
    organisation_id: uuid.UUID
    usager_id: uuid.UUID


class SignalementPerteRead(SignalementPerteBase):
    id: uuid.UUID
    organisation_id: uuid.UUID
    usager_id: uuid.UUID
    statut: StatutSignalement

    model_config = ConfigDict(from_attributes=True)


class SignalementPersonnelRead(SignalementPerteRead):
    """
    Vue réservée au personnel connecté : le signalement avec les coordonnées de la personne,
    pour qu'un agent puisse la contacter ou la reconnaître au guichet. Ces coordonnées ne sont
    JAMAIS renvoyées par la déclaration publique (POST /signalements/).
    """

    usager_nom: Optional[str] = None
    usager_telephone: str
