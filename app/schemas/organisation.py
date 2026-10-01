"""
Schémas Pydantic pour la ressource Organisation.

Contrairement au modèle SQLAlchemy (app/models/organisation.py), qui décrit
comment les données sont stockées dans PostgreSQL, ces schémas décrivent
le format des données tel qu'il est échangé avec l'extérieur, via l'API :
ce qu'un client a le droit d'envoyer, et ce que l'API renvoie en retour.
"""

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import SecteurOrganisation


class OrganisationBase(BaseModel):
    """Champs communs à la création et à la lecture d'une organisation."""

    nom: str
    secteur: SecteurOrganisation
    consultation_distance: bool = False
    delai_retention_jours: int = 90


class OrganisationCreate(OrganisationBase):
    """Format attendu en entrée lors de la création d'une organisation.
    Hérite de tous les champs de OrganisationBase sans rien y ajouter :
    on garde néanmoins une classe séparée pour pouvoir, plus tard,
    y ajouter des champs propres à la création sans toucher à OrganisationBase."""
    pass


class OrganisationRead(OrganisationBase):
    """Format renvoyé par l'API : reprend les champs de base et y ajoute
    l'identifiant unique, généré par la base de données."""

    id: uuid.UUID

    # Autorise Pydantic à construire ce schéma directement à partir d'un
    # objet SQLAlchemy (ex. : OrganisationRead.model_validate(organisation_sql)),
    # plutôt que depuis un simple dictionnaire.
    model_config = ConfigDict(from_attributes=True)
