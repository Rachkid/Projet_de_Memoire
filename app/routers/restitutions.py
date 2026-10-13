"""
Points d'accès de l'API pour la restitution d'un objet à son propriétaire
(cahier des charges, section 5.1.4). Le contrôle du détail caché est le
verrou anti-fraude : sans validation, aucune restitution n'est créée.

AVERTISSEMENT : l'identité de l'agent est ici transmise dans la requête
(agent_id), comme aux étapes précédentes. Tant que l'authentification par
jeton (JWT) n'est pas en place, n'importe qui connaissant cet identifiant
peut se faire passer pour l'agent. Cette protection est prévue à l'étape
« Authentification » ; elle est INDISPENSABLE avant toute mise en production,
en particulier pour l'endpoint qui révèle le détail caché.
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
from app.schemas.restitution import DetailCacheRead, RestitutionCreate, RestitutionRead

router = APIRouter(prefix="/restitutions", tags=["Restitutions"])


def _agent_autorise(db: Session, agent_id: uuid.UUID, objet: Objet) -> Utilisateur:
    """Vérifie que l'agent existe, a le droit de restitution et est de la même organisation."""
    agent = db.get(Utilisateur, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent introuvable")
    if not agent.droit_restitution:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet agent ne dispose pas du droit de restitution.",
        )
    if agent.organisation_id != objet.organisation_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet agent n'appartient pas à l'organisation propriétaire de l'objet.",
        )
    return agent


@router.get("/detail-cache/{objet_id}", response_model=DetailCacheRead)
def lire_detail_cache(objet_id: uuid.UUID, agent_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Réservé à l'agent de restitution : lui permet de comparer la réponse du
    demandeur avec le détail caché enregistré. Ne figure dans aucune autre
    réponse de l'API.
    """
    objet = db.get(Objet, objet_id)
    if objet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    _agent_autorise(db, agent_id, objet)
    return DetailCacheRead(objet_id=objet.id, detail_cache=objet.detail_cache)


@router.post("/", response_model=RestitutionRead, status_code=status.HTTP_201_CREATED)
def restituer_objet(payload: RestitutionCreate, db: Session = Depends(get_db)):
    """Valide la remise d'un objet à son propriétaire, après contrôle anti-fraude."""
    objet = db.get(Objet, payload.objet_id)
    if objet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    if objet.statut in (StatutObjet.RESTITUE.value, StatutObjet.ARCHIVE.value):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cet objet a déjà été restitué ou archivé.",
        )

    _agent_autorise(db, payload.agent_id, objet)

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
        date_heure=datetime.now(timezone.utc),  # fixée par le serveur
    )
    objet.statut = StatutObjet.RESTITUE.value
    db.add(restitution)
    db.commit()
    db.refresh(restitution)
    return restitution
