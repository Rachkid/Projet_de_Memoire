"""
Consultation du journal d'audit (étape 16), réservée aux administrateurs.

Un administrateur ne voit que les traces de son organisation ; le super-administrateur voit tout
(et peut filtrer par organisation). Le journal est en lecture seule : aucune route ne le modifie.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RoleUtilisateur
from app.models.journal_audit import JournalAudit
from app.models.utilisateur import Utilisateur
from app.security import exiger_administrateur

router = APIRouter(prefix="/audit", tags=["Journal d'audit"])


@router.get("/")
def lire_journal(
    action: str | None = Query(None, max_length=50),
    organisation_id: uuid.UUID | None = None,
    limite: int = Query(100, ge=1, le=200),
    decalage: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """Dernières actions enregistrées, de la plus récente à la plus ancienne."""
    est_super = demandeur.role == RoleUtilisateur.SUPER_ADMINISTRATEUR.value
    requete = db.query(JournalAudit)
    if est_super:
        if organisation_id is not None:
            requete = requete.filter(JournalAudit.organisation_id == organisation_id)
    else:
        # Le paramètre organisation_id est ignoré : on ne sort jamais de son organisation.
        requete = requete.filter(JournalAudit.organisation_id == demandeur.organisation_id)
    if action:
        requete = requete.filter(JournalAudit.action == action)
    total = requete.count()
    lignes = requete.order_by(JournalAudit.date_heure.desc()).offset(decalage).limit(limite).all()

    noms = {}
    ids = {l.utilisateur_id for l in lignes if l.utilisateur_id}
    if ids:
        for u in db.query(Utilisateur).filter(Utilisateur.id.in_(ids)).all():
            noms[u.id] = u.nom
    return {
        "total": total,
        "lignes": [
            {
                "id": str(l.id),
                "date_heure": l.date_heure.isoformat(),
                "action": l.action,
                "acteur": noms.get(l.utilisateur_id),
                "cible": l.cible,
                "detail": l.detail,
                "adresse": l.adresse,
            }
            for l in lignes
        ],
    }
