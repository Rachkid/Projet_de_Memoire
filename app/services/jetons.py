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
                maintenant: datetime | None = None) -> str:
    """Fabrique un jeton signé contenant l'identifiant de l'utilisateur (« sub »)."""
    maintenant = maintenant or datetime.now(timezone.utc)
    contenu = {
        "sub": sujet,                                         # à qui appartient le jeton
        "iat": maintenant,                                    # émis à
        "exp": maintenant + timedelta(minutes=duree_minutes), # expire à
    }
    return jwt.encode(contenu, cle, algorithm=algorithme)


def lire_jeton(jeton: str, cle: str, algorithme: str) -> str | None:
    """
    Renvoie l'identifiant contenu dans le jeton, ou None si le jeton est
    invalide (mauvaise signature, expiré, mal formé, sans « sub »).

    On impose la liste des algorithmes acceptés (algorithms=[algorithme]) :
    sans cela, un attaquant pourrait présenter un jeton déclarant
    « alg: none » (aucune signature) et le faire accepter.
    """
    try:
        contenu = jwt.decode(jeton, cle, algorithms=[algorithme], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    sujet = contenu.get("sub")
    return sujet if isinstance(sujet, str) else None
