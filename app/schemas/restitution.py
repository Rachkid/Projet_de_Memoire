"""
Schémas Pydantic pour la ressource Restitution.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RestitutionBase(BaseModel):
    type_piece_identite: Optional[str] = None
    numero_piece: Optional[str] = None
    photo_proprietaire_url: Optional[str] = None
    date_heure: datetime
    detail_controle_valide: bool = False


class RestitutionCreate(RestitutionBase):
    objet_id: uuid.UUID
    agent_id: uuid.UUID
    usager_id: Optional[uuid.UUID] = None


class RestitutionRead(RestitutionBase):
    id: uuid.UUID
    objet_id: uuid.UUID
    agent_id: uuid.UUID
    usager_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
