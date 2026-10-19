"""
Calculs sur les couleurs de l'habillage d'une organisation (Étape 10).

Ce module ne dépend ni de FastAPI ni de la base de données (comme photos.py) :
il est donc facile à tester seul.

Pourquoi ces calculs ? Une organisation choisit librement ses couleurs. Sans
garde-fou, on pourrait obtenir du texte blanc sur un fond jaune, illisible.
Le serveur calcule donc lui-même quelle couleur de texte employer sur chaque
fond, et déduit des variantes (très sombre, très claire) de la couleur
principale pour que l'organisation n'ait qu'une ou deux couleurs à fournir.
"""

import colorsys
import re

_MOTIF = re.compile(r"^#[0-9a-fA-F]{6}$")

# Thème par défaut de Retrova, utilisé quand l'organisation n'a pas choisi ses couleurs.
PRINCIPALE_DEFAUT = "#1d4e89"
ACCENT_DEFAUT = "#d9730d"
FOND_DEFAUT = "#f7f8fa"

_BLANC = "#ffffff"
_SOMBRE_TEXTE = "#111827"


def normaliser(couleur: str) -> str:
    """Vérifie le format #RRGGBB strict et renvoie la couleur en minuscules."""
    if not isinstance(couleur, str) or not _MOTIF.match(couleur):
        raise ValueError("Couleur invalide : utilisez le format #RRGGBB (par exemple #1a2b3c).")
    return couleur.lower()


def _rgb(couleur: str) -> tuple[float, float, float]:
    return tuple(int(couleur[i:i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _hex(r: float, g: float, b: float) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(round(max(0.0, min(1.0, c)) * 255) for c in (r, g, b)))


def luminance(couleur: str) -> float:
    """Luminance relative (norme WCAG) : 0 = noir, 1 = blanc."""
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(couleur))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    """Rapport de contraste entre deux couleurs (de 1 à 21). 4,5 est le minimum conseillé pour du texte."""
    haut, bas = sorted((luminance(a), luminance(b)), reverse=True)
    return (haut + 0.05) / (bas + 0.05)


def texte_lisible_sur(fond: str) -> str:
    """Renvoie la couleur de texte (blanc ou quasi noir) la plus lisible sur ce fond."""
    return _BLANC if contraste(_BLANC, fond) >= contraste(_SOMBRE_TEXTE, fond) else _SOMBRE_TEXTE


def assombrir(couleur: str, luminosite: float = 0.12) -> str:
    """Variante très sombre de la couleur (même teinte) : en-têtes, voile sur la photo de fond."""
    h, _, s = colorsys.rgb_to_hls(*_rgb(couleur))
    return _hex(*colorsys.hls_to_rgb(h, luminosite, s))


def eclaircir(couleur: str, part: float = 0.35) -> str:
    """Mélange la couleur avec du blanc (part = proportion de blanc ajoutée)."""
    r, g, b = _rgb(couleur)
    return _hex(r + (1 - r) * part, g + (1 - g) * part, b + (1 - b) * part)


def teinte_claire(couleur: str) -> str:
    """Fond de page très clair, légèrement teinté de la couleur principale."""
    h, _, s = colorsys.rgb_to_hls(*_rgb(couleur))
    return _hex(*colorsys.hls_to_rgb(h, 0.96, min(s, 0.35)))


def calculer_theme(principale: str | None, accent: str | None, fond: str | None) -> dict:
    """
    Thème complet à partir des couleurs choisies (toutes facultatives).
    Ce que l'organisation ne fournit pas est déduit ou remplacé par le thème Retrova.
    """
    principale = principale or PRINCIPALE_DEFAUT
    accent = accent or (eclaircir(principale) if principale != PRINCIPALE_DEFAUT else ACCENT_DEFAUT)
    fond = fond or (teinte_claire(principale) if principale != PRINCIPALE_DEFAUT else FOND_DEFAUT)
    sombre = assombrir(principale)
    return {
        "principale": principale,
        "accent": accent,
        "fond": fond,
        "sombre": sombre,
        "texte_sur_principale": texte_lisible_sur(principale),
        "texte_sur_accent": texte_lisible_sur(accent),
        "texte_sur_sombre": texte_lisible_sur(sombre),
        "texte_sur_fond": texte_lisible_sur(fond),
    }
