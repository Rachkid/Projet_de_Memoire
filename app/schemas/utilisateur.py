"""
Schémas Pydantic pour la ressource Utilisateur (agents, administrateurs).

Point de sécurité important : le mot de passe en clair n'apparaît que dans
le schéma de création (UtilisateurCreate), jamais dans le schéma de lecture
(UtilisateurRead) — l'API ne doit jamais renvoyer de mot de passe, ni même
sa version chiffrée, dans ses réponses.
"""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import RoleUtilisateur


class UtilisateurBase(BaseModel):
    nom: str
    role: RoleUtilisateur
    organisation_id: uuid.UUID
    droit_enregistrement: bool = False
    droit_restitution: bool = False


class UtilisateurCreate(UtilisateurBase):
    """Lors de la création, on reçoit un mot de passe en clair : il sera
    chiffré dans le router avant d'être transmis au modèle SQLAlchemy
    (voir app/models/utilisateur.py, champ mot_de_passe_hash)."""

    mot_de_passe: str


class UtilisateurRead(UtilisateurBase):
    id: uuid.UUID

    model_config = ConfigDict(from_attributes=True)
