"""
Sécurité de l'application : mots de passe, jetons et contrôle des droits.

Les « dépendances » ci-dessous (get_utilisateur_courant, exiger_...) se branchent
sur une route avec Depends(...). FastAPI les exécute AVANT la route : si la
personne n'est pas connectée ou n'a pas le droit requis, la route n'est jamais
exécutée et une erreur 401 ou 403 est renvoyée.

Principe important : les DROITS ne sont pas stockés dans le jeton, mais relus
dans la base à chaque requête. Si un administrateur retire un droit ou
désactive un compte, l'effet est immédiat, sans attendre l'expiration du jeton.
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.enums import RoleUtilisateur
from app.models.utilisateur import Utilisateur
from app.services.jetons import creer_jeton, lire_jeton

# bcrypt : algorithme volontairement lent, recommandé pour les mots de passe.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Empreinte d'un mot de passe bidon, utilisée à la connexion quand l'identifiant
# n'existe pas : on fait alors quand même un calcul bcrypt, pour que la réponse
# prenne le même temps. Sans cela, un attaquant pourrait deviner quels
# identifiants existent en mesurant le temps de réponse.
_EMPREINTE_FACTICE = pwd_context.hash("mot-de-passe-factice")

# Indique à Swagger (/docs) où se connecter : c'est ce qui fait apparaître
# le bouton « Authorize ».
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return pwd_context.hash(mot_de_passe)


def verifier_mot_de_passe(mot_de_passe: str, utilisateur: Utilisateur | None) -> bool:
    """Vérifie un mot de passe ; prend le même temps que l'utilisateur existe ou non."""
    if utilisateur is None:
        pwd_context.verify(mot_de_passe, _EMPREINTE_FACTICE)
        return False
    return pwd_context.verify(mot_de_passe, utilisateur.mot_de_passe_hash)


def creer_jeton_acces(utilisateur: Utilisateur) -> str:
    return creer_jeton(
        sujet=str(utilisateur.id),
        cle=settings.secret_key,
        algorithme=settings.algorithm,
        duree_minutes=settings.access_token_expire_minutes,
    )


def _non_authentifie() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Connexion requise ou session expirée.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_utilisateur_courant(
    jeton: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> Utilisateur:
    """Identifie la personne connectée à partir du jeton présenté."""
    sujet = lire_jeton(jeton, settings.secret_key, settings.algorithm)
    if sujet is None:
        raise _non_authentifie()
    try:
        utilisateur_id = uuid.UUID(sujet)
    except ValueError:
        raise _non_authentifie()
    utilisateur = db.get(Utilisateur, utilisateur_id)
    # Compte supprimé ou désactivé : le jeton, même valide, ne donne plus rien.
    if utilisateur is None or not utilisateur.actif:
        raise _non_authentifie()
    return utilisateur


def _interdit(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def exiger_enregistrement(utilisateur: Utilisateur = Depends(get_utilisateur_courant)) -> Utilisateur:
    if not utilisateur.droit_enregistrement:
        raise _interdit("Vous ne disposez pas du droit d'enregistrement.")
    return utilisateur


def exiger_restitution(utilisateur: Utilisateur = Depends(get_utilisateur_courant)) -> Utilisateur:
    if not utilisateur.droit_restitution:
        raise _interdit("Vous ne disposez pas du droit de restitution.")
    return utilisateur


def exiger_administrateur(utilisateur: Utilisateur = Depends(get_utilisateur_courant)) -> Utilisateur:
    if utilisateur.role not in (RoleUtilisateur.ADMINISTRATEUR.value, RoleUtilisateur.SUPER_ADMINISTRATEUR.value):
        raise _interdit("Réservé aux administrateurs.")
    return utilisateur


def exiger_super_administrateur(utilisateur: Utilisateur = Depends(get_utilisateur_courant)) -> Utilisateur:
    if utilisateur.role != RoleUtilisateur.SUPER_ADMINISTRATEUR.value:
        raise _interdit("Réservé au super-administrateur.")
    return utilisateur
