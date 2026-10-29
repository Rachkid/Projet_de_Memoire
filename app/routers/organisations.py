"""
Points d'accès de l'API pour la ressource Organisation.

C'est le tout premier router du projet : une organisation doit exister
avant que l'on puisse y rattacher des utilisateurs ou des objets (chapitre 3,
section 3.3 : toutes les autres tables dépendent d'organisation_id).
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.models.enums import RoleUtilisateur
from app.schemas.organisation import OrganisationCreate, OrganisationRead, OrganisationUpdate
from app.security import exiger_administrateur, exiger_super_administrateur
from app.services import audit
from app.services.habillage import enregistrer_fond, enregistrer_logo, supprimer_ancien
from app.services.photos import PhotoInvalide

# Un APIRouter regroupe les points d'accès liés à une même ressource.
# prefix="/organisations" évite de le répéter devant chaque route ci-dessous.
# tags=["Organisations"] ne sert qu'à regrouper ces routes dans la
# documentation interactive générée automatiquement par FastAPI (/docs).
router = APIRouter(prefix="/organisations", tags=["Organisations"])

# Logos et photos de fond : publics (ils s'affichent sur la page de connexion, avant
# toute identification). Rangés dans un sous-dossier par organisation.
DOSSIER_ORGANISATIONS = Path(settings.upload_dir) / "organisations"
URL_ORGANISATIONS = "/fichiers/organisations"


def _slug_pris(db: Session, slug: str, sauf_id: uuid.UUID | None = None) -> bool:
    requete = db.query(Organisation).filter(Organisation.slug == slug)
    if sauf_id is not None:
        requete = requete.filter(Organisation.id != sauf_id)
    return db.query(requete.exists()).scalar()


def _erreur_slug_pris() -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet identifiant d'adresse est déjà utilisé.")


@router.post("/", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
def creer_organisation(
    payload: OrganisationCreate,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(exiger_super_administrateur),
):
    """Crée une nouvelle organisation cliente. Réservé au super-administrateur."""
    if payload.slug is not None and _slug_pris(db, payload.slug):
        raise _erreur_slug_pris()
    organisation = Organisation(**payload.model_dump())
    db.add(organisation)
    try:
        db.commit()
    except IntegrityError:  # deux créations simultanées avec le même identifiant
        db.rollback()
        raise _erreur_slug_pris()
    db.refresh(organisation)
    return organisation


@router.get("/", response_model=list[OrganisationRead])
def lister_organisations(db: Session = Depends(get_db)):
    """Liste les organisations (publique : le portail en a besoin pour que l'usager choisisse la sienne)."""
    return db.query(Organisation).all()


@router.get("/par-slug/{slug}", response_model=OrganisationRead)
def obtenir_organisation_par_slug(slug: str, db: Session = Depends(get_db)):
    """
    Retrouve une organisation à partir de l'identifiant court de son adresse (ex. : « iat »).
    Publique : c'est ce qui permet à la page de connexion et au portail d'être
    habillés aux couleurs de l'organisation AVANT que la personne se connecte.
    """
    organisation = db.query(Organisation).filter(Organisation.slug == slug.lower()).first()
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return organisation


@router.get("/{organisation_id}", response_model=OrganisationRead)
def obtenir_organisation(organisation_id: uuid.UUID, db: Session = Depends(get_db)):
    """Récupère une organisation précise à partir de son identifiant."""
    organisation = db.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return organisation


def _organisation_modifiable(db: Session, organisation_id: uuid.UUID, demandeur: Utilisateur) -> tuple[Organisation, bool]:
    """
    Charge l'organisation visée par une modification et dit si le demandeur est super-administrateur.
    Un administrateur ne voit que sa propre organisation : pour toute autre, elle « n'existe pas » (404).
    """
    est_super = demandeur.role == RoleUtilisateur.SUPER_ADMINISTRATEUR.value
    if not est_super and demandeur.organisation_id != organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    organisation = db.get(Organisation, organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")
    return organisation, est_super


@router.patch("/{organisation_id}", response_model=OrganisationRead)
def modifier_organisation(
    organisation_id: uuid.UUID,
    payload: OrganisationUpdate,
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """
    Modifie une organisation (seuls les champs envoyés changent).
    - Le super-administrateur peut tout modifier.
    - Un administrateur ne modifie QUE sa propre organisation : ses paramètres de
      fonctionnement (consultation à distance, délai de rétention) et son habillage
      (couleurs). Le nom et l'identifiant court d'adresse restent réservés au
      super-administrateur : changer l'identifiant casserait les liens et les QR codes déjà diffusés.
    - Pour une couleur, envoyer null remet la couleur par défaut.
    """
    organisation, est_super = _organisation_modifiable(db, organisation_id, demandeur)

    modifications = payload.model_dump(exclude_unset=True)
    if not modifications:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie.")
    if "nom" in modifications and not est_super:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seul le super-administrateur peut renommer une organisation.")
    if "slug" in modifications:
        if not est_super:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seul le super-administrateur peut modifier l'identifiant d'adresse.")
        if _slug_pris(db, modifications["slug"], sauf_id=organisation.id):
            raise _erreur_slug_pris()
    for champ, valeur in modifications.items():
        setattr(organisation, champ, valeur)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _erreur_slug_pris()
    db.refresh(organisation)
    audit.tracer(db, audit.ORGANISATION_MODIFIEE, acteur=demandeur, organisation_id=organisation.id,
                 cible=organisation.slug, detail="Champs modifiés : " + ", ".join(sorted(modifications)))
    return organisation


async def _lire_fichier(fichier: UploadFile) -> bytes:
    # On lit au plus (limite + 1) octets : un fichier énorme n'est jamais chargé en mémoire.
    contenu = await fichier.read(settings.photo_max_octets + 1)
    if len(contenu) > settings.photo_max_octets:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image trop lourde (maximum {settings.photo_max_octets // (1024 * 1024)} Mo).",
        )
    return contenu


@router.post("/{organisation_id}/logo", response_model=OrganisationRead)
async def envoyer_logo(
    organisation_id: uuid.UUID,
    fichier: UploadFile = File(...),
    retirer_fond_blanc: bool = Form(False),
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """
    Envoie (ou remplace) le logo de l'organisation. Formats acceptés : JPEG, PNG, WEBP
    (pas de SVG). `retirer_fond_blanc` rend transparent le fond blanc autour du logo,
    utile pour un logo livré en JPEG. Mêmes droits que PATCH /organisations/{id} pour l'habillage.
    """
    organisation, _ = _organisation_modifiable(db, organisation_id, demandeur)
    contenu = await _lire_fichier(fichier)
    dossier = DOSSIER_ORGANISATIONS / str(organisation.id)
    try:
        nom = enregistrer_logo(contenu, dossier, retirer_fond_blanc)
    except PhotoInvalide as erreur:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erreur))
    ancien = organisation.logo_url
    organisation.logo_url = f"{URL_ORGANISATIONS}/{organisation.id}/{nom}"
    db.commit()
    supprimer_ancien(ancien, URL_ORGANISATIONS, DOSSIER_ORGANISATIONS)  # après le commit : en cas d'échec, l'ancien reste intact
    db.refresh(organisation)
    audit.tracer(db, audit.ORGANISATION_MODIFIEE, acteur=demandeur, organisation_id=organisation.id, cible=organisation.slug, detail="Logo remplacé")
    return organisation


@router.post("/{organisation_id}/fond", response_model=OrganisationRead)
async def envoyer_fond(
    organisation_id: uuid.UUID,
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
    demandeur: Utilisateur = Depends(exiger_administrateur),
):
    """Envoie (ou remplace) la photo de fond de l'organisation (réduite à 1920 px de large au plus)."""
    organisation, _ = _organisation_modifiable(db, organisation_id, demandeur)
    contenu = await _lire_fichier(fichier)
    dossier = DOSSIER_ORGANISATIONS / str(organisation.id)
    try:
        nom = enregistrer_fond(contenu, dossier)
    except PhotoInvalide as erreur:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erreur))
    ancien = organisation.fond_url
    organisation.fond_url = f"{URL_ORGANISATIONS}/{organisation.id}/{nom}"
    db.commit()
    supprimer_ancien(ancien, URL_ORGANISATIONS, DOSSIER_ORGANISATIONS)
    db.refresh(organisation)
    audit.tracer(db, audit.ORGANISATION_MODIFIEE, acteur=demandeur, organisation_id=organisation.id, cible=organisation.slug, detail="Photo de fond remplacée")
    return organisation
