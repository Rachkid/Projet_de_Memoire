"""
Catégories personnalisées (étape 19) : l'administrateur d'une organisation ajoute ses propres catégories d'objets,
en plus de la liste standard. Réservé aux administrateurs, limité à leur organisation.

Règles : un nom ne peut pas être modifié ni supprimé (des objets l'utilisent) : on peut seulement changer l'icône,
les traductions ou désactiver la catégorie. Pas de doublon (accents et majuscules ignorés), 30 au maximum.
"""

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.limites import adresse_client
from app.models.categorie_personnalisee import CategoriePersonnalisee
from app.models.utilisateur import Utilisateur
from app.schemas.categorie import CategorieCreate, CategorieRead, CategorieUpdate, cle_nom
from app.security import exiger_administrateur
from app.services import audit
from app.services.categories import toutes_les_categories_standard

router = APIRouter(prefix="/categories", tags=["Catégories personnalisées"])

MAXIMUM_PAR_ORGANISATION = 30


@router.get("/", response_model=list[CategorieRead])
def lister_categories(db: Session = Depends(get_db), admin: Utilisateur = Depends(exiger_administrateur)):
    """Toutes les catégories personnalisées de l'organisation, actives ou non."""
    return (
        db.query(CategoriePersonnalisee)
        .filter(CategoriePersonnalisee.organisation_id == admin.organisation_id)
        .order_by(CategoriePersonnalisee.nom_cle)
        .all()
    )


@router.post("/", response_model=CategorieRead, status_code=status.HTTP_201_CREATED)
def creer_categorie(
    requete: Request,
    payload: CategorieCreate,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_administrateur),
):
    existantes = db.query(CategoriePersonnalisee).filter(CategoriePersonnalisee.organisation_id == admin.organisation_id).all()
    if len(existantes) >= MAXIMUM_PAR_ORGANISATION:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Maximum {MAXIMUM_PAR_ORGANISATION} catégories personnalisées. Désactivez-en une qui ne sert plus.")
    cle = cle_nom(payload.nom)
    if cle in {cle_nom(n) for n in toutes_les_categories_standard()} or any(c.nom_cle == cle for c in existantes):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une catégorie portant ce nom existe déjà.")
    categorie = CategoriePersonnalisee(
        organisation_id=admin.organisation_id, nom=payload.nom, nom_cle=cle, icone=payload.icone,
        traductions=json.dumps(payload.traductions or {}, ensure_ascii=False),
    )
    db.add(categorie)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Une catégorie portant ce nom existe déjà.")
    db.refresh(categorie)
    audit.tracer(db, audit.CATEGORIE_AJOUTEE, acteur=admin, organisation_id=admin.organisation_id, cible=categorie.nom, adresse=adresse_client(requete))
    return categorie


@router.patch("/{categorie_id}", response_model=CategorieRead)
def modifier_categorie(
    requete: Request,
    categorie_id: uuid.UUID,
    payload: CategorieUpdate,
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_administrateur),
):
    categorie = db.get(CategoriePersonnalisee, categorie_id)
    if categorie is None or categorie.organisation_id != admin.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catégorie introuvable")
    modifications = payload.model_dump(exclude_unset=True)
    if not modifications:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie.")
    if "icone" in modifications:
        categorie.icone = modifications["icone"]
    if "traductions" in modifications:
        categorie.traductions = json.dumps(modifications["traductions"] or {}, ensure_ascii=False)
    if "actif" in modifications:
        categorie.actif = modifications["actif"]
    db.commit()
    db.refresh(categorie)
    audit.tracer(db, audit.CATEGORIE_MODIFIEE, acteur=admin, organisation_id=admin.organisation_id, cible=categorie.nom,
                 detail="Champs modifiés : " + ", ".join(sorted(modifications)), adresse=adresse_client(requete))
    return categorie
