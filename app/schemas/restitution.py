"""
Schémas Pydantic pour la ressource Restitution.

Deux choix de conception importants :
- la date et l'heure de la restitution ne sont pas fournies par le client :
  elles sont fixées par le serveur, pour qu'elles ne puissent pas être
  falsifiées (traçabilité) ;
- l'usager et la pièce d'identité sont obligatoires : on ne remet jamais un
  objet sans savoir à qui (cahier des charges, section 5.1.4).
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RestitutionBase(BaseModel):
    type_piece_identite: str = Field(min_length=1, max_length=50)
    numero_piece: str = Field(min_length=1, max_length=50)
    photo_proprietaire_url: Optional[str] = None
    # Facultatif (écoles) : le matricule de l'étudiant à qui l'objet est remis.
    matricule_etudiant: Optional[str] = Field(default=None, max_length=50)

    @field_validator("matricule_etudiant", mode="before")
    @classmethod
    def matricule_valide(cls, valeur):
        if valeur is None:
            return None
        valeur = str(valeur).strip()
        if valeur == "":
            return None
        # Lettres, chiffres, espace, point, tiret, souligné et barre oblique : assez pour les formats de matricule usuels.
        if not re.fullmatch(r"[\w .\-/]{1,50}", valeur):
            raise ValueError("Matricule invalide : lettres, chiffres, point, tiret ou barre oblique seulement.")
        return valeur


class RestitutionCreate(RestitutionBase):
    objet_id: uuid.UUID
    # L'agent est la personne connectée (jeton) : il n'est plus envoyé ici.
    usager_id: uuid.UUID
    # Verdict de l'agent après avoir comparé la réponse du demandeur au
    # détail caché de l'objet.
    detail_controle_valide: bool


class RestitutionRead(RestitutionBase):
    id: uuid.UUID
    objet_id: uuid.UUID
    agent_id: uuid.UUID
    usager_id: Optional[uuid.UUID] = None
    date_heure: datetime
    detail_controle_valide: bool

    model_config = ConfigDict(from_attributes=True)


class DetailCacheRead(BaseModel):
    """Réponse de l'endpoint réservé aux agents : le détail caché d'un objet."""

    objet_id: uuid.UUID
    detail_cache: Optional[str] = None
