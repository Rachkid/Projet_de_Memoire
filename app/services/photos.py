"""
Traitement et stockage des photos envoyées par les agents.

Ce module ne dépend ni de FastAPI ni de la base de données : il reçoit les
octets bruts d'un fichier et un dossier, et renvoie le nom du fichier créé.
Il est donc facile à tester seul.

Principe de sécurité : on ne fait JAMAIS confiance au fichier reçu (nom,
extension, type annoncé). On l'ouvre réellement avec Pillow : si ce n'est pas
une vraie image, il est rejeté. Puis on le RE-ENCODE en JPEG, ce qui
  - garantit que le fichier stocké est bien une image et rien d'autre ;
  - supprime les métadonnées cachées (EXIF), dont la position GPS du téléphone ;
  - réduit la taille (les photos de téléphone font souvent plusieurs Mo).
Le nom du fichier est généré par le serveur : celui de l'utilisateur est ignoré.
"""

import re
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

FORMATS_ACCEPTES = {"JPEG", "PNG", "WEBP"}
# Limite de pixels : protège contre les « bombes de décompression » (petit
# fichier qui s'étend en une image gigantesque et fait planter le serveur).
Image.MAX_IMAGE_PIXELS = 40_000_000

_MOTIF_NOM = re.compile(r"^[0-9a-f]{32}\.jpg$")


class PhotoInvalide(ValueError):
    """Le fichier reçu n'est pas une image acceptable."""


def nom_fichier_valide(nom: str) -> bool:
    """Vrai uniquement pour un nom généré par ce module (empêche '../' et autres ruses)."""
    return bool(_MOTIF_NOM.match(nom))


def ouvrir_image_verifiee(contenu: bytes) -> Image.Image:
    """
    Ouvre réellement le fichier avec Pillow et le décode entièrement. Lève
    PhotoInvalide si ce n'est pas une image JPEG, PNG ou WEBP saine. Partagé par
    les photos d'objets et par les logos/photos de fond des organisations.
    """
    if not contenu:
        raise PhotoInvalide("Fichier vide.")
    try:
        image = Image.open(BytesIO(contenu))
        if image.format not in FORMATS_ACCEPTES:
            raise PhotoInvalide("Format non accepté : utilisez JPEG, PNG ou WEBP.")
        image.load()  # force le décodage complet : détecte les fichiers tronqués ou piégés
    except PhotoInvalide:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError, ValueError):
        raise PhotoInvalide("Le fichier n'est pas une image valide.")
    return ImageOps.exif_transpose(image)  # remet l'image à l'endroit selon l'orientation du téléphone


def enregistrer_photo(contenu: bytes, dossier: Path, cote_max: int) -> str:
    """Vérifie, nettoie et enregistre une photo. Renvoie le nom du fichier créé."""
    image = ouvrir_image_verifiee(contenu)
    image = image.convert("RGB")  # JPEG ne gère pas la transparence
    image.thumbnail((cote_max, cote_max))

    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"{uuid.uuid4().hex}.jpg"
    image.save(dossier / nom, format="JPEG", quality=85, optimize=True)  # sans EXIF
    return nom
