"""
Alertes de la cloche (étape 15 bis).

Les alertes ne sont PAS stockées : elles sont recalculées à chaque appel à partir des données
réelles. Il n'y a donc rien à « marquer comme lu » côté serveur et aucun risque d'alerte périmée.
Le navigateur, lui, retient ce que la personne a déjà vu (voir agent.js).

Deux types pour l'instant :
- « correspondances » (tout le personnel) : des déclarations pour lesquelles un objet pouvant
  correspondre a été trouvé, et qui attendent qu'on s'en occupe ;
- « fin_retention » (administrateurs) : des objets gardés depuis presque la durée de conservation
  de l'organisation, à rendre, à détruire ou à archiver.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.enums import RoleUtilisateur, StatutObjet, StatutSignalement
from app.models.objet import Objet
from app.models.organisation import Organisation
from app.models.signalement_perte import SignalementPerte
from app.models.utilisateur import Utilisateur
from app.services.statistiques import PREAVIS_RETENTION_JOURS


def alertes_pour(db: Session, utilisateur: Utilisateur) -> list[dict]:
    org_id = utilisateur.organisation_id
    alertes: list[dict] = []

    a_traiter = (
        db.query(func.count(SignalementPerte.id))
        .filter(SignalementPerte.organisation_id == org_id, SignalementPerte.statut == StatutSignalement.CORRESPONDANCE_TROUVEE.value)
        .scalar()
        or 0
    )
    if a_traiter:
        alertes.append({
            "type": "correspondances",
            "niveau": "info",
            "nombre": a_traiter,
            "titre": "1 déclaration avec un objet correspondant" if a_traiter == 1 else f"{a_traiter} déclarations avec un objet correspondant",
            "detail": "Ces personnes attendent d'être prévenues ou reçues.",
            "lien": "#pertes",
        })

    est_admin = utilisateur.role in (RoleUtilisateur.ADMINISTRATEUR.value, RoleUtilisateur.SUPER_ADMINISTRATEUR.value)
    if est_admin:
        organisation = db.get(Organisation, org_id)
        delai = (organisation.delai_retention_jours if organisation else None) or 90
        limite = datetime.now(timezone.utc) - timedelta(days=max(delai - PREAVIS_RETENTION_JOURS, 0))
        proches = (
            db.query(func.count(Objet.id))
            .filter(Objet.organisation_id == org_id, Objet.statut == StatutObjet.EN_ATTENTE.value, Objet.date_heure_decouverte <= limite)
            .scalar()
            or 0
        )
        if proches:
            alertes.append({
                "type": "fin_retention",
                "niveau": "attention",
                "nombre": proches,
                "titre": "1 objet bientôt en fin de conservation" if proches == 1 else f"{proches} objets bientôt en fin de conservation",
                "detail": f"Gardés depuis presque {delai} jours.",
                "lien": "#bord",
            })
    return alertes
