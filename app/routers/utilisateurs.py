"""
Points d'accès de l'API pour la ressource Utilisateur (agents, administrateurs).

Règles d'accès (étape 8) :
- le super-administrateur gère tous les comptes de toutes les organisations ;
- un administrateur gère uniquement les AGENTS de sa propre organisation ;
- un agent n'a accès à aucune gestion de comptes.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RoleUtilisateur
from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.schemas.utilisateur import UtilisateurCreate, UtilisateurRead
from app.security import exiger_administrateur, hacher_mot_de_passe

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])


def _est_super(utilisateur: Utilisateur) -> bool:
    return utilisateur.role == RoleUtilisateur.SUPER_ADMINISTRATEUR.value


@router.post("/", response_model=UtilisateurRead, status_code=status.HTTP_201_CREATED)
def creer_utilisateur(
    payload: UtilisateurCreate,
    db: Session = Depends(get_db),
    createur: Utilisateur = Depends(exiger_administrateur),
):
    """Crée un compte. Le mot de passe est chiffré avant d'être stocké."""
    if not _est_super(createur):
        # Un administrateur ne crée que des agents, et seulement dans son organisation.
        if payload.role != RoleUtilisateur.AGENT:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez créer que des agents.")
        if payload.organisation_id != createur.organisation_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez créer des comptes que dans votre organisation.")

    if db.get(Organisation, payload.organisation_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")

    donnees = payload.model_dump(exclude={"mot_de_passe"})
    utilisateur = Utilisateur(**donnees, mot_de_passe_hash=hacher_mot_de_passe(payload.mot_de_passe))
    db.add(utilisateur)
    try:
        db.commit()
    except IntegrityError:  # identifiant déjà pris (contrainte d'unicité de la base)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet identifiant existe déjà.")
    db.refresh(utilisateur)
    return utilisateur


@router.get("/", response_model=list[UtilisateurRead])
def lister_utilisateurs(
    organisation_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """Liste les comptes. Un administrateur ne voit que ceux de son organisation."""
    if not _est_super(demandeur):
        if organisation_id is not None and organisation_id != demandeur.organisation_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Accès limité à votre organisation.")
        organisation_id = demandeur.organisation_id
    requete = db.query(Utilisateur)
    if organisation_id is not None:
        requete = requete.filter(Utilisateur.organisation_id == organisation_id)
    return requete.all()


@router.patch("/{utilisateur_id}/desactiver", response_model=UtilisateurRead)
def desactiver_utilisateur(
    utilisateur_id: uuid.UUID,
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """
    Désactive un compte (départ d'un agent, téléphone perdu...). Effet immédiat :
    son jeton, même encore valide, ne donne plus aucun accès (voir security.py).
    """
    cible = db.get(Utilisateur, utilisateur_id)
    # Pour un administrateur, un compte d'une autre organisation « n'existe pas ».
    if cible is None or (not _est_super(demandeur) and cible.organisation_id != demandeur.organisation_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    if cible.id == demandeur.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vous ne pouvez pas désactiver votre propre compte.")
    if not _est_super(demandeur) and cible.role != RoleUtilisateur.AGENT.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vous ne pouvez désactiver que des agents.")
    cible.actif = False
    db.commit()
    db.refresh(cible)
    return cible
