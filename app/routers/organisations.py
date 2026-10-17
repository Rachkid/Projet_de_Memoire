"""
Points d'accès de l'API pour la ressource Organisation.

C'est le tout premier router du projet : une organisation doit exister
avant que l'on puisse y rattacher des utilisateurs ou des objets (chapitre 3,
section 3.3 : toutes les autres tables dépendent d'organisation_id).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.models.enums import RoleUtilisateur
from app.schemas.organisation import OrganisationCreate, OrganisationRead, OrganisationUpdate
from app.security import exiger_administrateur, exiger_super_administrateur

# Un APIRouter regroupe les points d'accès liés à une même ressource.
# prefix="/organisations" évite de le répéter devant chaque route ci-dessous.
# tags=["Organisations"] ne sert qu'à regrouper ces routes dans la
# documentation interactive générée automatiquement par FastAPI (/docs).
router = APIRouter(prefix="/organisations", tags=["Organisations"])


@router.post("/", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
def creer_organisation(
    payload: OrganisationCreate,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(exiger_super_administrateur),
):
    """Crée une nouvelle organisation cliente. Réservé au super-administrateur."""
    organisation = Organisation(**payload.model_dump())
    db.add(organisation)
    db.commit()
    db.refresh(organisation)
    return organisation


@router.get("/", response_model=list[OrganisationRead])
def lister_organisations(db: Session = Depends(get_db)):
    """Liste les organisations (publique : le portail en a besoin pour que l'usager choisisse la sienne)."""
    return db.query(Organisation).all()


@router.get("/{organisation_id}", response_model=OrganisationRead)
def obtenir_organisation(organisation_id: uuid.UUID, db: Session = Depends(get_db)):
    """Récupère une organisation précise à partir de son identifiant."""
    organisation = db.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return organisation


@router.patch("/{organisation_id}", response_model=OrganisationRead)
def modifier_organisation(
    organisation_id: uuid.UUID,
    payload: OrganisationUpdate,
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """
    Modifie une organisation (seuls les champs envoyés changent).
    - Le super-administrateur peut tout modifier (nom, consultation à distance, délai de rétention).
    - Un administrateur ne modifie QUE sa propre organisation, et seulement ses
      paramètres de fonctionnement (consultation à distance, délai de rétention) :
      le nom de l'organisation reste réservé au super-administrateur.
    """
    est_super = demandeur.role == RoleUtilisateur.SUPER_ADMINISTRATEUR.value
    if not est_super and demandeur.organisation_id != organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    organisation = db.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")

    modifications = payload.model_dump(exclude_unset=True)
    if not modifications:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie.")
    if "nom" in modifications and not est_super:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seul le super-administrateur peut renommer une organisation.")
    for champ, valeur in modifications.items():
        setattr(organisation, champ, valeur)
    db.commit()
    db.refresh(organisation)
    return organisation
