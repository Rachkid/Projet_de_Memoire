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
from app.schemas.organisation import OrganisationCreate, OrganisationRead

# Un APIRouter regroupe les points d'accès liés à une même ressource.
# prefix="/organisations" évite de le répéter devant chaque route ci-dessous.
# tags=["Organisations"] ne sert qu'à regrouper ces routes dans la
# documentation interactive générée automatiquement par FastAPI (/docs).
router = APIRouter(prefix="/organisations", tags=["Organisations"])


@router.post("/", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
def creer_organisation(payload: OrganisationCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle organisation (établissement ou compagnie) cliente du système."""
    organisation = Organisation(**payload.model_dump())
    db.add(organisation)
    db.commit()
    db.refresh(organisation)
    return organisation


@router.get("/", response_model=list[OrganisationRead])
def lister_organisations(db: Session = Depends(get_db)):
    """Liste toutes les organisations enregistrées (vue réservée, à terme, au super-administrateur)."""
    return db.query(Organisation).all()


@router.get("/{organisation_id}", response_model=OrganisationRead)
def obtenir_organisation(organisation_id: uuid.UUID, db: Session = Depends(get_db)):
    """Récupère une organisation précise à partir de son identifiant."""
    organisation = db.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return organisation
