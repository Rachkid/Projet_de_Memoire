"""
Schémas Pydantic pour la ressource Usager (personnes extérieures sans compte).
"""

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UsagerBase(BaseModel):
    telephone: str
    nom: Optional[str] = None


class UsagerCreate(UsagerBase):
    pass


class UsagerRead(UsagerBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
