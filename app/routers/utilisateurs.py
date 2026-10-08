"""
Points d'accès de l'API pour la ressource Utilisateur (agents, administrateurs).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.utilisateur import Utilisateur
from app.schemas.utilisateur import UtilisateurCreate, UtilisateurRead

router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])

# bcrypt est l'algorithme de chiffrement recommandé pour les mots de passe :
# il est volontairement lent, ce qui le rend très résistant aux tentatives
# de deviner un mot de passe par essais successifs (force brute).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/", response_model=UtilisateurRead, status_code=status.HTTP_201_CREATED)
def creer_utilisateur(payload: UtilisateurCreate, db: Session = Depends(get_db)):
    """
    Crée un nouvel agent ou administrateur. Le mot de passe reçu en clair
    (payload.mot_de_passe) n'est jamais stocké tel quel : il est chiffré
    avant d'être placé dans mot_de_passe_hash (voir app/models/utilisateur.py).
    """
    donnees = payload.model_dump(exclude={"mot_de_passe"})
    utilisateur = Utilisateur(
        **donnees,
        mot_de_passe_hash=pwd_context.hash(payload.mot_de_passe),
    )
    db.add(utilisateur)
    db.commit()
    db.refresh(utilisateur)
    return utilisateur


@router.get("/", response_model=list[UtilisateurRead])
def lister_utilisateurs(organisation_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    """Liste les utilisateurs, éventuellement filtrés par organisation."""
    requete = db.query(Utilisateur)
    if organisation_id is not None:
        requete = requete.filter(Utilisateur.organisation_id == organisation_id)
    return requete.all()
