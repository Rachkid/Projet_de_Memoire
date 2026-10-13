"""
Points d'accès de l'API pour les signalements de perte (cahier des charges,
section 5.1.3). Un usager déclare ce qu'il a perdu ; le système cherche
immédiatement dans les objets déjà trouvés, puis continuera de surveiller
chaque nouvel objet enregistré (voir routers/objets.py).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organisation import Organisation
from app.models.signalement_perte import SignalementPerte
from app.models.usager import Usager
from app.schemas.objet import ObjetRead
from app.schemas.signalement_perte import SignalementPerteCreate, SignalementPerteRead
from app.services.rapprochement import objets_correspondants, traiter_nouveau_signalement

router = APIRouter(prefix="/signalements", tags=["Signalements de perte"])


@router.post("/", response_model=SignalementPerteRead, status_code=status.HTTP_201_CREATED)
def declarer_perte(payload: SignalementPerteCreate, db: Session = Depends(get_db)):
    """Enregistre un signalement puis lance le rapprochement automatique."""
    if db.get(Organisation, payload.organisation_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    if db.get(Usager, payload.usager_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usager introuvable")

    signalement = SignalementPerte(**payload.model_dump())
    db.add(signalement)
    db.commit()
    db.refresh(signalement)

    traiter_nouveau_signalement(db, signalement)
    db.refresh(signalement)
    return signalement


@router.get("/", response_model=list[SignalementPerteRead])
def lister_signalements(organisation_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    """Liste les signalements, filtrables par organisation (isolation multi-tenant)."""
    requete = db.query(SignalementPerte)
    if organisation_id is not None:
        requete = requete.filter(SignalementPerte.organisation_id == organisation_id)
    return requete.all()


@router.get("/{signalement_id}/correspondances", response_model=list[ObjetRead])
def correspondances(signalement_id: uuid.UUID, db: Session = Depends(get_db)):
    """Objets actuellement en attente qui correspondent à ce signalement."""
    signalement = db.get(SignalementPerte, signalement_id)
    if signalement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signalement introuvable")
    return objets_correspondants(db, signalement)
