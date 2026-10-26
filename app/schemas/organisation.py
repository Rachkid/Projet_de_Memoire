"""
Schémas Pydantic pour la ressource Organisation.

Contrairement au modèle SQLAlchemy (app/models/organisation.py), qui décrit
comment les données sont stockées dans PostgreSQL, ces schémas décrivent
le format des données tel qu'il est échangé avec l'extérieur, via l'API :
ce qu'un client a le droit d'envoyer, et ce que l'API renvoie en retour.
"""

import re
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.models.enums import SecteurOrganisation
from app.services.couleurs import calculer_theme, normaliser

_MOTIF_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

# Mots qui ne peuvent pas servir d'identifiant court : ils sont déjà pris par des
# adresses de l'application (/docs, /auth, /fichiers...). Sans cette liste,
# une organisation nommée « docs » rendrait la documentation inaccessible.
SLUGS_RESERVES = {
    "docs", "redoc", "openapi", "fichiers", "auth", "organisations", "utilisateurs", "usagers",
    "objets", "signalements", "restitutions", "photos", "admin", "api", "static", "assets",
    "login", "portail", "affichage", "retrova", "statistiques", "historique",
}


def verifier_slug(valeur: str) -> str:
    """Identifiant court d'adresse : minuscules, chiffres et tirets (2 à 50 caractères)."""
    valeur = valeur.strip().lower()
    if not (2 <= len(valeur) <= 50) or not _MOTIF_SLUG.match(valeur):
        raise ValueError("2 à 50 caractères : lettres minuscules, chiffres et tirets (ex. : iat, bus-rimbo).")
    if valeur in SLUGS_RESERVES:
        raise ValueError("Cet identifiant est réservé par l'application.")
    return valeur


def verifier_couleur(valeur: Optional[str]) -> Optional[str]:
    return None if valeur is None else normaliser(valeur)


class OrganisationBase(BaseModel):
    """Champs communs à la création et à la lecture d'une organisation."""

    nom: str
    secteur: SecteurOrganisation
    consultation_distance: bool = False
    delai_retention_jours: int = 90


class OrganisationCreate(OrganisationBase):
    """Format attendu en entrée lors de la création d'une organisation.
    L'identifiant court d'adresse (slug) et les couleurs sont facultatifs ; le logo
    et la photo de fond s'envoient ensuite par leurs propres routes (fichiers)."""

    slug: Optional[str] = None
    couleur_principale: Optional[str] = None
    couleur_accent: Optional[str] = None
    couleur_fond: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def slug_valide(cls, valeur):
        return None if valeur is None else verifier_slug(valeur)

    @field_validator("couleur_principale", "couleur_accent", "couleur_fond")
    @classmethod
    def couleur_valide(cls, valeur):
        return verifier_couleur(valeur)


class OrganisationUpdate(BaseModel):
    """
    Modification d'une organisation (PATCH). Le secteur n'est pas modifiable :
    il détermine le fonctionnement de l'organisation (véhicules, locaux...).
    """

    nom: Optional[str] = None
    slug: Optional[str] = None
    consultation_distance: Optional[bool] = None
    delai_retention_jours: Optional[int] = Field(default=None, ge=1, le=3650)
    # Couleurs : une valeur null REMET la couleur par défaut (contrairement aux autres champs).
    couleur_principale: Optional[str] = None
    couleur_accent: Optional[str] = None
    couleur_fond: Optional[str] = None

    @field_validator("couleur_principale", "couleur_accent", "couleur_fond")
    @classmethod
    def couleur_valide(cls, valeur):
        return verifier_couleur(valeur)

    @field_validator("slug")
    @classmethod
    def slug_valide(cls, valeur):
        if valeur is None:
            raise ValueError("Ce champ ne peut pas être vide.")
        return verifier_slug(valeur)

    @field_validator("nom", "consultation_distance", "delai_retention_jours")
    @classmethod
    def pas_de_valeur_nulle(cls, valeur):
        if valeur is None:
            raise ValueError("Ce champ ne peut pas être vide.")
        return valeur

    @field_validator("nom")
    @classmethod
    def nom_non_vide(cls, valeur: str) -> str:
        valeur = valeur.strip()
        if not valeur:
            raise ValueError("Le nom ne peut pas être vide.")
        return valeur


class ThemeRead(BaseModel):
    """Thème prêt à l'emploi pour les pages : les couleurs choisies, complétées par celles
    que le serveur déduit, et la couleur de texte lisible sur chaque fond."""

    principale: str
    accent: str
    fond: str
    sombre: str
    texte_sur_principale: str
    texte_sur_accent: str
    texte_sur_sombre: str
    texte_sur_fond: str


class OrganisationRead(OrganisationBase):
    """Format renvoyé par l'API : reprend les champs de base et y ajoute
    l'identifiant unique, généré par la base de données, ainsi que l'habillage."""

    id: uuid.UUID
    slug: Optional[str] = None
    logo_url: Optional[str] = None
    fond_url: Optional[str] = None
    couleur_principale: Optional[str] = None
    couleur_accent: Optional[str] = None
    couleur_fond: Optional[str] = None

    @computed_field  # calculé à la lecture : jamais stocké, donc toujours cohérent avec les couleurs choisies
    @property
    def theme(self) -> ThemeRead:
        return ThemeRead(**calculer_theme(self.couleur_principale, self.couleur_accent, self.couleur_fond))

    # Autorise Pydantic à construire ce schéma directement à partir d'un
    # objet SQLAlchemy (ex. : OrganisationRead.model_validate(organisation_sql)),
    # plutôt que depuis un simple dictionnaire.
    model_config = ConfigDict(from_attributes=True)
