"""
Points d'accès de l'API pour la restitution d'un objet à son propriétaire
(cahier des charges, section 5.1.4). Le contrôle du détail caché est le
verrou anti-fraude : sans validation, aucune restitution n'est créée.

Accès : toutes les routes exigent d'être connecté avec le droit de
restitution. L'agent est identifié par son jeton (plus d'agent_id dans les
requêtes) et ne peut agir que sur les objets de sa propre organisation.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import StatutObjet
from app.models.objet import Objet
from app.models.restitution import Restitution
from app.models.usager import Usager
from app.models.utilisateur import Utilisateur
from app.security import exiger_restitution
from app.schemas.restitution import DetailCacheRead, RestitutionCreate, RestitutionRead

router = APIRouter(prefix="/restitutions", tags=["Restitutions"])


def _objet_de_mon_organisation(db: Session, objet_id: uuid.UUID, agent: Utilisateur) -> Objet:
    """Charge l'objet ; s'il appartient à une autre organisation, il « n'existe pas »."""
    objet = db.get(Objet, objet_id)
    if objet is None or objet.organisation_id != agent.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    return objet


@router.get("/detail-cache/{objet_id}", response_model=DetailCacheRead)
def lire_detail_cache(
    objet_id: uuid.UUID,
    db: Session = Depends(get_db),
    agent: Utilisateur = Depends(exiger_restitution),
):
    """
    Réservé à l'agent de restitution : lui permet de comparer la réponse du
    demandeur avec le détail caché enregistré. Ne figure dans aucune autre
    réponse de l'API.
    """
    objet = _objet_de_mon_organisation(db, objet_id, agent)
    return DetailCacheRead(objet_id=objet.id, detail_cache=objet.detail_cache)


@router.post("/", response_model=RestitutionRead, status_code=status.HTTP_201_CREATED)
def restituer_objet(
    payload: RestitutionCreate,
    db: Session = Depends(get_db),
    agent: Utilisateur = Depends(exiger_restitution),
):
    """Valide la remise d'un objet à son propriétaire, après contrôle anti-fraude."""
    objet = _objet_de_mon_organisation(db, payload.objet_id, agent)
    if objet.statut in (StatutObjet.RESTITUE.value, StatutObjet.ARCHIVE.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet objet a déjà été restitué ou archivé.",
        )

    if db.get(Usager, payload.usager_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usager introuvable")

    # Verrou anti-fraude : le détail caché n'a pas été confirmé -> refus,
    # aucune restitution n'est créée et le statut de l'objet ne change pas.
    if not payload.detail_controle_valide:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restitution refusée : le détail caché n'a pas été confirmé.",
        )

    restitution = Restitution(
        **payload.model_dump(),
        agent_id=agent.id,  # l'agent connecté, pas une valeur fournie par le client
        date_heure=datetime.now(timezone.utc),  # fixée par le serveur
    )
    objet.statut = StatutObjet.RESTITUE.value
    db.add(restitution)
    db.commit()
    db.refresh(restitution)
    return restitution
