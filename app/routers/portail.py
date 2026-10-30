"""
Points d'accès de l'API réservés au portail public (Étape 11).

Le portail est la page que voit un usager SANS compte (par exemple /iat) : il
déclare un objet perdu et, si l'organisation l'a autorisé, consulte les objets
trouvés. Ces routes sont publiques ; elles sont donc écrites avec prudence :
on n'y expose que ce qui est nécessaire, jamais le détail caché d'un objet.

La déclaration de perte elle-même réutilise les routes existantes
POST /usagers/ puis POST /signalements/ (Étape 6).
"""

import json
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.enums import StatutObjet
from app.models.objet import Objet
from app.models.organisation import Organisation
from app.schemas.objet import ObjetPublicRead
from app.models.categorie_personnalisee import CategoriePersonnalisee
from app.schemas.categorie import CategoriePubliqueRead
from app.services.categories import CATEGORIES, categories_pour

router = APIRouter(prefix="/portail", tags=["Portail public"])

# Plafond de sécurité : une page publique ne doit pas pouvoir tout aspirer d'un coup.
LIMITE_OBJETS = 200


@router.get("/categories", response_model=list[str])
def lister_categories():
    """Catégories proposées dans les formulaires (mêmes mots pour l'usager et pour l'agent)."""
    return CATEGORIES


@router.get("/{slug}/categories", response_model=list[str])
def lister_categories_organisation(slug: str, db: Session = Depends(get_db)):
    """Catégories proposées par une organisation : communes + celles de son secteur (éducation ou transport)."""
    organisation = db.query(Organisation).filter(Organisation.slug == slug.strip().lower()).first()
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return categories_pour(organisation.secteur, [c.nom for c in _personnalisees_actives(db, organisation)])


def _personnalisees_actives(db: Session, organisation: Organisation) -> list[CategoriePersonnalisee]:
    return (
        db.query(CategoriePersonnalisee)
        .filter(CategoriePersonnalisee.organisation_id == organisation.id, CategoriePersonnalisee.actif.is_(True))
        .order_by(CategoriePersonnalisee.nom_cle)
        .all()
    )


@router.get("/{slug}/categories/personnalisees", response_model=list[CategoriePubliqueRead])
def categories_personnalisees(slug: str, db: Session = Depends(get_db)):
    """Catégories ajoutées par l'organisation (nom, icône, traductions) : pour les afficher dans la bonne langue."""
    organisation = db.query(Organisation).filter(Organisation.slug == slug.strip().lower()).first()
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return [
        CategoriePubliqueRead(nom=c.nom, icone=c.icone, traductions=json.loads(c.traductions) if c.traductions else {})
        for c in _personnalisees_actives(db, organisation)
    ]


@router.get("/{slug}/objets", response_model=list[ObjetPublicRead])
def objets_exposes(slug: str, db: Session = Depends(get_db)):
    """
    Objets trouvés visibles par le public, pour l'organisation désignée par son identifiant court.

    - 404 si l'identifiant n'existe pas ;
    - 403 si l'organisation n'a pas activé la « consultation à distance » : la règle est
      appliquée ICI, côté serveur, et non seulement en cachant un bouton dans la page ;
    - seuls les objets « en attente » sont montrés (ni réclamés, ni restitués, ni archivés).
    """
    organisation = db.query(Organisation).filter(Organisation.slug == slug.strip().lower()).first()
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    if not organisation.consultation_distance:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cette organisation n'expose pas ses objets trouvés en ligne.",
        )
    return (
        db.query(Objet)
        .filter(Objet.organisation_id == organisation.id, Objet.statut == StatutObjet.EN_ATTENTE.value)
        .order_by(Objet.date_heure_decouverte.desc())
        .limit(LIMITE_OBJETS)
        .all()
    )


@router.get("/{slug}/qrcode")
def qrcode_portail(slug: str, request: Request, db: Session = Depends(get_db)):
    """
    Image du code QR qui mène au portail public de l'organisation (Étape 13). Elle s'affiche en bas
    de l'écran du hall : un visiteur la scanne avec son téléphone et déclare sa perte sans rien saisir.
    L'image ne contient qu'une adresse publique ; elle est produite à la volée, jamais stockée.
    """
    organisation = db.query(Organisation).filter(Organisation.slug == slug.strip().lower()).first()
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    racine = (settings.adresse_publique or str(request.base_url)).rstrip("/")
    image = qrcode.make(f"{racine}/{organisation.slug}", box_size=12, border=2)
    tampon = BytesIO()
    image.save(tampon, format="PNG")
    tampon.seek(0)
    return StreamingResponse(tampon, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
