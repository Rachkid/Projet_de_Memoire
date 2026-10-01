"""
Schémas Pydantic pour la ressource SignalementPerte.
"""

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatutSignalement


class SignalementPerteBase(BaseModel):
    categorie: str
    description: Optional[str] = None


class SignalementPerteCreate(SignalementPerteBase):
    organisation_id: uuid.UUID
    usager_id: uuid.UUID


class SignalementPerteRead(SignalementPerteBase):
    id: uuid.UUID
    organisation_id: uuid.UUID
    usager_id: uuid.UUID
    statut: StatutSignalement

    model_config = ConfigDict(from_attributes=True)
