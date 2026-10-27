"""
Création et lecture des jetons de connexion (JWT).

Un JWT est un petit texte signé que le serveur remet à l'agent après sa
connexion. L'agent le présente ensuite à chaque requête. Le serveur n'a pas
besoin de le stocker : il vérifie simplement la signature. Toute modification
du jeton par un tiers (changer l'identifiant, prolonger la date d'expiration)
invalide la signature et le jeton est rejeté.

Ce module ne dépend ni de FastAPI ni de la base de données : la clé, l'algorithme
et la durée lui sont passés en paramètres, ce qui le rend testable seul.
"""

from datetime import datetime, timedelta, timezone

import jwt


def creer_jeton(sujet: str, cle: str, algorithme: str, duree_minutes: int,
                maintenant: datetime | None = None, version: int = 0) -> str:
    """
    Fabrique un jeton signé contenant l'identifiant de l'utilisateur (« sub ») et le numéro de génération de
    ses sessions (« v », étape 16) : si le compte change de numéro, ce jeton n'est plus accepté.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    contenu = {
        "sub": sujet,                                         # à qui appartient le jeton
        "v": version,                                         # génération de session
        "iat": maintenant,                                    # émis à
        "exp": maintenant + timedelta(minutes=duree_minutes), # expire à
    }
    return jwt.encode(contenu, cle, algorithm=algorithme)


def lire_jeton_complet(jeton: str, cle: str, algorithme: str) -> tuple[str, int] | None:
    """
    Renvoie (identifiant, génération de session) contenus dans le jeton, ou None si le jeton est
    invalide (mauvaise signature, expiré, mal formé, sans « sub »). Un jeton émis avant l'étape 16,
    sans « v », est lu comme génération 0.

    On impose la liste des algorithmes acceptés (algorithms=[algorithme]) :
    sans cela, un attaquant pourrait présenter un jeton déclarant
    « alg: none » (aucune signature) et le faire accepter.
    """
    try:
        contenu = jwt.decode(jeton, cle, algorithms=[algorithme], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    sujet = contenu.get("sub")
    version = contenu.get("v", 0)
    if not isinstance(sujet, str) or not isinstance(version, int) or isinstance(version, bool):
        return None
    return sujet, version


def lire_jeton(jeton: str, cle: str, algorithme: str) -> str | None:
    """Renvoie seulement l'identifiant contenu dans le jeton (ou None) : voir lire_jeton_complet."""
    lu = lire_jeton_complet(jeton, cle, algorithme)
    return lu[0] if lu else None
