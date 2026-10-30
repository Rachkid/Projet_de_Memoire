"""
Schémas de l'étape 19 : catégories personnalisées d'une organisation.

Le nom (français) est la valeur enregistrée sur les objets : il ne change jamais après la création.
Les traductions sont facultatives ; sans traduction, la langue affiche le nom français.
"""

import json
import re
import unicodedata
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

LANGUES_TRADUITES = ("en", "ha", "dje", "ar")
LONGUEUR_MAX = 60
# Lettres (toutes écritures), chiffres, espace et quelques signes courants. Pas de < > " ni de barre oblique inverse.
_MOTIF = re.compile(r"^[\w' ()/.&+-]+$", re.UNICODE)

# Icônes proposées : leur dessin est dans l'application (pas de fichier envoyé). Voir agent.js, affichage.js.
ICONES_CATALOGUE = (
    "autre", "telephone", "portefeuille", "cles", "sac", "documents", "carte bancaire", "vetement", "lunettes", "ordinateur",
    "ecouteurs ou baladeur", "montre", "bijou", "livre ou cahier", "tapis de priere", "casquette", "gourde", "chaussures",
    "carte d'identite", "passeport", "cle usb", "disque dur", "chargeur", "argent", "bracelet", "batterie", "clavier", "souris",
    "multiprise ou rallonge", "parfums", "boissons", "ustensiles de cuisine", "produits medicaux", "kit de maquillage",
    "outils de reparation", "pieces mecaniques", "outils de chantier", "materiel electrique", "bic", "calculatrice",
    "ico-ballon", "ico-casier", "ico-boite", "ico-cadenas", "ico-parapluie", "ico-ampoule", "ico-appareil photo", "ico-velo", "ico-plante", "ico-coeur", "ico-etoile", "ico-cadeau", "ico-reveil", "ico-tasse", "ico-couverts", "ico-biberon", "ico-cubes", "ico-voiture", "ico-moto", "ico-bus", "ico-valise", "ico-sac a dos", "ico-casque audio", "ico-micro", "ico-haut-parleur", "ico-tablette", "ico-ecran", "ico-imprimante", "ico-manette", "ico-crayon", "ico-regle", "ico-ciseaux", "ico-loupe", "ico-drapeau", "ico-trophee", "ico-pilule", "ico-thermometre", "ico-lune", "ico-chapeau", "ico-cravate", "ico-ceinture", "ico-dossier", "ico-enveloppe", "ico-panier",
)


def cle_nom(nom: str) -> str:
    """Nom sans accents, en minuscules et espaces simples : sert à repérer les doublons."""
    sans_accent = unicodedata.normalize("NFD", nom).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sans_accent.strip().lower())


def _nettoyer(valeur: str, nom_champ: str) -> str:
    valeur = re.sub(r"\s+", " ", valeur.strip())
    if not valeur:
        raise ValueError(f"{nom_champ} ne peut pas être vide.")
    if len(valeur) > LONGUEUR_MAX:
        raise ValueError(f"{nom_champ} : {LONGUEUR_MAX} caractères au maximum.")
    if not _MOTIF.match(valeur):
        raise ValueError(f"{nom_champ} : lettres, chiffres, espaces et . ' ( ) / & + - seulement.")
    return valeur


def _verifier_traductions(valeur):
    if valeur is None:
        return None
    if not isinstance(valeur, dict):
        raise ValueError("Traductions invalides.")
    resultat = {}
    for code, texte in valeur.items():
        if code not in LANGUES_TRADUITES:
            raise ValueError(f"Langue inconnue : {code}.")
        if texte is None or not str(texte).strip():
            continue  # champ laissé vide : la langue affichera le nom français
        resultat[code] = _nettoyer(str(texte), "La traduction")
    return resultat


class CategorieCreate(BaseModel):
    nom: str
    icone: str = "autre"
    traductions: Optional[dict] = None

    @field_validator("nom")
    @classmethod
    def nom_valide(cls, valeur: str) -> str:
        valeur = _nettoyer(valeur, "Le nom")
        if cle_nom(valeur) in ("autre", ""):
            raise ValueError("Ce nom est réservé.")
        return valeur

    @field_validator("icone")
    @classmethod
    def icone_valide(cls, valeur: str) -> str:
        if valeur not in ICONES_CATALOGUE:
            raise ValueError("Icône inconnue.")
        return valeur

    @field_validator("traductions", mode="before")
    @classmethod
    def traductions_valides(cls, valeur):
        return _verifier_traductions(valeur)


class CategorieUpdate(BaseModel):
    """Le nom n'est volontairement pas modifiable : des objets enregistrés l'utilisent déjà."""

    icone: Optional[str] = None
    traductions: Optional[dict] = None
    actif: Optional[bool] = None

    @field_validator("icone")
    @classmethod
    def icone_valide(cls, valeur):
        if valeur is None or valeur not in ICONES_CATALOGUE:
            raise ValueError("Icône inconnue.")
        return valeur

    @field_validator("actif")
    @classmethod
    def actif_non_nul(cls, valeur):
        if valeur is None:
            raise ValueError("Ce champ ne peut pas être vide.")
        return valeur

    @field_validator("traductions", mode="before")
    @classmethod
    def traductions_valides(cls, valeur):
        return _verifier_traductions(valeur) if valeur is not None else {}


class CategorieRead(BaseModel):
    id: uuid.UUID
    nom: str
    icone: str
    traductions: dict
    actif: bool

    model_config = ConfigDict(from_attributes=True)

    @field_validator("traductions", mode="before")
    @classmethod
    def lire_traductions(cls, valeur):
        if valeur is None or valeur == "":
            return {}
        if isinstance(valeur, str):
            try:
                valeur = json.loads(valeur)
            except ValueError:
                return {}
        return valeur if isinstance(valeur, dict) else {}


class CategoriePubliqueRead(BaseModel):
    """Ce que le public voit d'une catégorie personnalisée active : son nom, son icône, ses traductions."""

    nom: str
    icone: str
    traductions: dict
