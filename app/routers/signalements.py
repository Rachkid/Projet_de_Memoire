"""
Points d'accès de l'API pour les signalements de perte (cahier des charges,
section 5.1.3). Un usager déclare ce qu'il a perdu ; le système cherche
immédiatement dans les objets déjà trouvés, puis continuera de surveiller
chaque nouvel objet enregistré (voir routers/objets.py).

Accès : la DÉCLARATION est publique (l'usager n'a pas de compte). La
CONSULTATION des signalements est réservée au personnel connecté, et limitée
à sa propre organisation.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import StatutSignalement
from app.models.organisation import Organisation
from app.models.signalement_perte import SignalementPerte
from app.models.usager import Usager
from app.models.utilisateur import Utilisateur
from app.schemas.objet import ObjetRead
from app.schemas.signalement_perte import SignalementPerteCreate, SignalementPerteRead, SignalementPersonnelRead
from app.security import get_utilisateur_courant
from app.services.rapprochement import objets_correspondants, traiter_nouveau_signalement

router = APIRouter(prefix="/signalements", tags=["Signalements de perte"])


@router.post("/", response_model=SignalementPerteRead, status_code=status.HTTP_201_CREATED)
def declarer_perte(payload: SignalementPerteCreate, db: Session = Depends(get_db)):
    """Enregistre un signalement (public) puis lance le rapprochement automatique."""
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


@router.get("/", response_model=list[SignalementPersonnelRead])
def lister_signalements(
    statut: StatutSignalement | None = None,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """
    Liste les signalements de l'organisation de la personne connectée (jamais ceux d'une autre),
    avec le nom et le téléphone de leur auteur. Sans filtre, les signalements clôturés sont omis.
    """
    requete = db.query(SignalementPerte).filter(SignalementPerte.organisation_id == personnel.organisation_id)
    if statut is not None:
        requete = requete.filter(SignalementPerte.statut == statut.value)
    else:
        requete = requete.filter(SignalementPerte.statut != StatutSignalement.CLOTURE.value)
    # Les correspondances d'abord : ce sont les personnes à prévenir ou à recevoir.
    signalements = sorted(requete.all(), key=lambda s: s.statut != StatutSignalement.CORRESPONDANCE_TROUVEE.value)
    return [
        SignalementPersonnelRead.model_validate(s).model_copy(
            update={"usager_nom": s.usager.nom, "usager_telephone": s.usager.telephone}
        )
        for s in signalements
    ]


@router.get("/{signalement_id}/correspondances", response_model=list[ObjetRead])
def correspondances(
    signalement_id: uuid.UUID,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """Objets actuellement en attente qui correspondent à ce signalement."""
    signalement = db.get(SignalementPerte, signalement_id)
    # Signalement d'une autre organisation : on répond « introuvable », pas « interdit »,
    # pour ne même pas révéler qu'il existe.
    if signalement is None or signalement.organisation_id != personnel.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signalement introuvable")
    return objets_correspondants(db, signalement)


@router.patch("/{signalement_id}/cloturer", response_model=SignalementPerteRead)
def cloturer_signalement(
    signalement_id: uuid.UUID,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """Clôture un signalement (l'usager a retrouvé son objet, ou ne le cherche plus)."""
    signalement = db.get(SignalementPerte, signalement_id)
    if signalement is None or signalement.organisation_id != personnel.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signalement introuvable")
    if signalement.statut == StatutSignalement.CLOTURE.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ce signalement est déjà clôturé.")
    signalement.statut = StatutSignalement.CLOTURE.value
    db.commit()
    db.refresh(signalement)
    return signalement
