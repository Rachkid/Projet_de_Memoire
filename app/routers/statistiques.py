"""
Tableau de bord (Étape 14) : chiffres agrégés, réservés aux administrateurs.

- un administrateur voit uniquement sa propre organisation ;
- le super-administrateur voit n'importe quelle organisation (?organisation_id=)
  et une comparaison de toutes les organisations (/statistiques/comparaison).
Aucune de ces routes ne renvoie d'objet ni de personne : seulement des totaux.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RoleUtilisateur
from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.security import exiger_administrateur, exiger_super_administrateur
from app.services.statistiques import statistiques_organisation

router = APIRouter(prefix="/statistiques", tags=["Statistiques"])


@router.get("/")
def tableau_de_bord(
    organisation_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_administrateur),
):
    """Chiffres d'une organisation. Un administrateur ne peut voir que la sienne."""
    est_super = admin.role == RoleUtilisateur.SUPER_ADMINISTRATEUR.value
    cible = organisation_id if (est_super and organisation_id) else admin.organisation_id
    organisation = db.get(Organisation, cible)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return statistiques_organisation(db, organisation)


@router.get("/comparaison")
def comparaison(db: Session = Depends(get_db), _super: Utilisateur = Depends(exiger_super_administrateur)):
    """Une ligne de chiffres par organisation (vue du super-administrateur)."""
    organisations = db.query(Organisation).order_by(Organisation.nom).all()
    lignes = []
    for o in organisations:
        s = statistiques_organisation(db, o)
        lignes.append({k: s[k] for k in (
            "organisation_id", "organisation_nom", "secteur", "objets_en_attente", "objets_restitues",
            "restitues_ce_mois", "declarations_en_cours", "taux_restitution", "delai_moyen_heures", "proches_fin_retention",
        )})
    return lignes
