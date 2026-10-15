"""
Schémas Pydantic pour la ressource Utilisateur (agents, administrateurs).

Point de sécurité important : le mot de passe en clair n'apparaît que dans
le schéma de création (UtilisateurCreate), jamais dans le schéma de lecture
(UtilisateurRead) — l'API ne doit jamais renvoyer de mot de passe, ni même
sa version chiffrée, dans ses réponses.
"""

import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import RoleUtilisateur

_MOTIF_IDENTIFIANT = re.compile(r"^[a-z0-9._-]{3,50}$")


class UtilisateurBase(BaseModel):
    nom: str
    role: RoleUtilisateur
    organisation_id: uuid.UUID
    droit_enregistrement: bool = False
    droit_restitution: bool = False


class UtilisateurCreate(UtilisateurBase):
    """Lors de la création, on reçoit un mot de passe en clair : il sera
    chiffré dans le router avant d'être transmis au modèle SQLAlchemy."""

    identifiant: str
    mot_de_passe: str

    @field_validator("identifiant")
    @classmethod
    def identifiant_valide(cls, valeur: str) -> str:
        valeur = valeur.strip().lower()
        if not _MOTIF_IDENTIFIANT.match(valeur):
            raise ValueError("3 à 50 caractères : lettres, chiffres, point, tiret ou souligné.")
        return valeur

    @field_validator("mot_de_passe")
    @classmethod
    def mot_de_passe_valide(cls, valeur: str) -> str:
        if len(valeur) < 8:
            raise ValueError("Le mot de passe doit contenir au moins 8 caractères.")
        # bcrypt ne lit que les 72 premiers octets : au-delà, il les ignorerait
        # en silence. On refuse plutôt que de laisser croire que tout compte.
        if len(valeur.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe est trop long (72 octets maximum).")
        return valeur


class UtilisateurRead(UtilisateurBase):
    id: uuid.UUID
    identifiant: str
    actif: bool

    model_config = ConfigDict(from_attributes=True)
