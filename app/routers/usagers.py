"""
Points d'accès de l'API pour la ressource Usager (personnes sans compte).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usager import Usager
from app.schemas.usager import UsagerCreate, UsagerRead

router = APIRouter(prefix="/usagers", tags=["Usagers"])


@router.post("/", response_model=UsagerRead, status_code=status.HTTP_201_CREATED)
def creer_ou_recuperer_usager(payload: UsagerCreate, db: Session = Depends(get_db)):
    """
    Si un usager existe déjà avec ce numéro de téléphone, on le renvoie
    directement plutôt que d'en créer un doublon. C'est ce mécanisme simple
    qui permet de relier l'historique d'une même personne au fil du temps
    (mémoire, chapitre 3, section 3.2.2), sans jamais lui demander de créer
    un compte ni de se souvenir d'un identifiant.
    """
    usager_existant = db.query(Usager).filter(Usager.telephone == payload.telephone).first()
    if usager_existant is not None:
        return usager_existant

    usager = Usager(**payload.model_dump())
    db.add(usager)
    db.commit()
    db.refresh(usager)
    return usager


@router.get("/", response_model=list[UsagerRead])
def lister_usagers(db: Session = Depends(get_db)):
    """Liste tous les usagers connus du système (profil réservé à l'administration)."""
    return db.query(Usager).all()
