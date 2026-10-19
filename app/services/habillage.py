"""
Traitement et stockage du logo et de la photo de fond d'une organisation (Étape 10).

Comme photos.py, ce module ne dépend ni de FastAPI ni de la base de données.
Même principe de sécurité : le fichier reçu n'est jamais stocké tel quel. Il
est ouvert avec Pillow puis RE-ENCODÉ :
  - le logo en PNG (la transparence est conservée), sans métadonnées ;
  - la photo de fond en JPEG, réduite en largeur, sans métadonnées.
Les SVG sont volontairement refusés (FORMATS_ACCEPTES de photos.py) : un SVG peut
contenir du code qui s'exécuterait dans le navigateur de toute personne qui
affiche la page de l'organisation.
Les noms de fichiers sont générés par le serveur ; chaque envoi crée un NOUVEAU
nom, ce qui évite que le navigateur continue d'afficher l'ancienne image en cache.
"""

import uuid
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from app.services.photos import ouvrir_image_verifiee

LOGO_COTE_MAX = 800
FOND_LARGEUR_MAX = 1920

# Couleur-repère temporaire utilisée pour détecter le fond blanc extérieur d'un logo.
_REPERE = (255, 0, 255, 255)


def supprimer_fond_blanc(image: Image.Image, tolerance: int = 40) -> Image.Image:
    """
    Rend transparent le fond blanc AUTOUR du logo, sans toucher au blanc situé à
    l'intérieur (un « remplissage par diffusion » part des quatre coins et
    s'arrête au premier contour du dessin). Utile pour un logo livré en JPEG,
    format qui ne gère pas la transparence.
    """
    image = image.convert("RGBA")
    largeur, hauteur = image.size
    travail = image.copy()
    for coin in ((0, 0), (largeur - 1, 0), (0, hauteur - 1), (largeur - 1, hauteur - 1)):
        # On ne diffuse que si le coin est bien (presque) blanc : un logo déjà
        # sur fond coloré ne doit pas être effacé.
        if all(c >= 255 - tolerance for c in travail.getpixel(coin)[:3]):
            ImageDraw.floodfill(travail, coin, _REPERE, thresh=tolerance)
    donnees = [(0, 0, 0, 0) if px == _REPERE else orig for px, orig in zip(travail.getdata(), image.getdata())]
    resultat = Image.new("RGBA", image.size)
    resultat.putdata(donnees)
    return resultat


def rogner_marges(image: Image.Image, marge: float = 0.05) -> Image.Image:
    """
    Coupe les marges vides autour du logo (Étape 11). Beaucoup de logos sont livrés au centre
    d'une grande image blanche ou transparente : sans ce rognage, ils apparaissent minuscules
    dans la plaque de l'accueil et dans la barre du haut du portail.
    - image avec transparence : le contenu est tout ce qui n'est pas transparent ;
    - image opaque : le contenu est tout ce qui n'est pas (presque) blanc.
    Une petite marge (5 %) est conservée pour que le dessin ne touche pas le bord.
    """
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    if alpha.getextrema()[0] < 255:
        contenu = alpha.point(lambda v: 255 if v > 16 else 0)
    else:
        r, g, b = rgba.getchannel("R"), rgba.getchannel("G"), rgba.getchannel("B")
        plus_sombre = ImageChops.darker(ImageChops.darker(r, g), b)
        contenu = plus_sombre.point(lambda v: 0 if v >= 245 else 255)
    boite = contenu.getbbox()
    if boite is None:  # image entièrement vide ou blanche : on ne touche à rien
        return rgba
    gauche, haut, droite, bas = boite
    pas = max(2, round(max(droite - gauche, bas - haut) * marge))
    boite = (max(0, gauche - pas), max(0, haut - pas), min(rgba.width, droite + pas), min(rgba.height, bas + pas))
    return rgba.crop(boite)


def enregistrer_logo(contenu: bytes, dossier: Path, retirer_fond_blanc: bool = False) -> str:
    """Vérifie et enregistre un logo (PNG, marges vides coupées). Renvoie le nom du fichier créé."""
    image = ouvrir_image_verifiee(contenu)
    image = supprimer_fond_blanc(image) if retirer_fond_blanc else image.convert("RGBA")
    image = rogner_marges(image)
    image.thumbnail((LOGO_COTE_MAX, LOGO_COTE_MAX))
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"logo-{uuid.uuid4().hex}.png"
    image.save(dossier / nom, format="PNG", optimize=True)
    return nom


def enregistrer_fond(contenu: bytes, dossier: Path) -> str:
    """Vérifie et enregistre la photo de fond (JPEG, 1920 px de large au plus)."""
    image = ouvrir_image_verifiee(contenu).convert("RGB")
    if image.width > FOND_LARGEUR_MAX:  # on ne fait que réduire : agrandir une photo n'améliore rien
        image = image.resize((FOND_LARGEUR_MAX, round(image.height * FOND_LARGEUR_MAX / image.width)), Image.LANCZOS)
    dossier.mkdir(parents=True, exist_ok=True)
    nom = f"fond-{uuid.uuid4().hex}.jpg"
    image.save(dossier / nom, format="JPEG", quality=82, optimize=True, progressive=True)
    return nom


def supprimer_ancien(url: str | None, racine_url: str, racine_disque: Path) -> None:
    """
    Efface l'ancien fichier après un remplacement, pour ne pas accumuler des
    images inutiles. Ne supprime que ce qui se trouve réellement dans le dossier
    des organisations (jamais un chemin fourni de l'extérieur).
    """
    if not url or not url.startswith(racine_url + "/"):
        return
    chemin = (racine_disque / url[len(racine_url) + 1:]).resolve()
    if racine_disque.resolve() in chemin.parents and chemin.is_file():
        chemin.unlink()
