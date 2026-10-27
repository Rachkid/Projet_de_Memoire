"""
Branchement de la limitation des tentatives sur les routes (étape 16).

Les « dépendances » de ce fichier s'ajoutent à une route avec Depends(...) : FastAPI les exécute avant la
route, et renvoie l'erreur 429 (« trop de requêtes ») si la personne a dépassé son quota.
"""

from fastapi import HTTPException, Request, status

from app.config import settings
from app.services.limitation import Limiteur

# Échecs de connexion, par (adresse + identifiant) puis par adresse seule.
echecs_connexion = Limiteur(settings.limite_connexion_essais, settings.limite_connexion_minutes * 60)
echecs_connexion_adresse = Limiteur(settings.limite_connexion_par_adresse, settings.limite_connexion_minutes * 60)
# Requêtes aux formulaires publics, par adresse.
requetes_publiques = Limiteur(settings.limite_declarations, settings.limite_declarations_minutes * 60)


def adresse_client(requete: Request) -> str:
    """
    Adresse de la personne qui appelle. Derrière un relais de confiance, c'est la DERNIÈRE adresse de
    X-Forwarded-For (celle que le relais a lui-même ajoutée : les précédentes peuvent être inventées par le client).
    """
    if settings.proxy_de_confiance:
        transmis = requete.headers.get("x-forwarded-for", "")
        if transmis:
            derniere = transmis.split(",")[-1].strip()
            if derniere:
                return derniere
    return requete.client.host if requete.client else "inconnue"


def trop_de_tentatives(secondes: int) -> HTTPException:
    minutes = max(1, -(-secondes // 60))
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Trop de tentatives. Réessayez dans {minutes} minute{'s' if minutes > 1 else ''}.",
        headers={"Retry-After": str(secondes)},
    )


def limiter_requetes_publiques(requete: Request) -> None:
    """Dépendance des formulaires publics : refuse au-delà du quota, sinon compte la requête."""
    cle = adresse_client(requete)
    attente = requetes_publiques.attente(cle)
    if attente:
        raise trop_de_tentatives(attente)
    requetes_publiques.enregistrer(cle)
