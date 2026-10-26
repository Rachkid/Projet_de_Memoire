"""
Schémas Pydantic pour la ressource SignalementPerte.
"""

import re
import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import StatutSignalement


class SignalementPerteBase(BaseModel):
    categorie: str
    description: Optional[str] = None
    date_perte: Optional[date] = None
    lieu_approximatif: Optional[str] = None


# Forme simple d'une adresse e-mail : « quelque chose @ domaine . extension », sans espace.
# (Pas de bibliothèque de validation en plus : le but est d'écarter les fautes de frappe évidentes ;
# la vraie preuve qu'une adresse existe, c'est le courriel de confirmation qui y arrive.)
MOTIF_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class SignalementPerteCreate(SignalementPerteBase):
    organisation_id: uuid.UUID
    usager_id: uuid.UUID
    # Facultatif. Jamais renvoyé par l'API (voir SignalementPerteRead).
    email: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def verifier_email(cls, valeur):
        if valeur is None:
            return None
        valeur = str(valeur).strip().lower()
        if valeur == "":
            return None
        if len(valeur) > 254 or not MOTIF_EMAIL.match(valeur):
            raise ValueError("Adresse e-mail invalide")
        return valeur


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

    @classmethod
    def depuis_signalement(cls, signalement) -> "SignalementPersonnelRead":
        """
        Construit la vue du personnel à partir d'un signalement de la base. Le nom et le téléphone
        viennent de l'usager lié : ils n'existent pas sur le signalement lui-même, il faut donc les
        ajouter à la main (valider directement l'objet de la base échouerait : champ manquant).
        """
        return cls(
            **SignalementPerteRead.model_validate(signalement).model_dump(),
            usager_nom=signalement.usager.nom,
            usager_telephone=signalement.usager.telephone,
        )
