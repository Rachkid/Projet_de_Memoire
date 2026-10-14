"""
Points d'accès pour l'envoi et la consultation des photos (cahier des charges,
sections 5.1.1 et 5.1.4).

Deux types de photos, aux règles différentes :
- photos d'OBJETS : publiques (elles s'affichent sur l'écran d'affichage et le
  portail pour que les usagers reconnaissent leurs affaires). Servies
  directement comme fichiers statiques sous /fichiers/objets/.
- photos de PROPRIÉTAIRES (prises lors de la restitution) : données
  personnelles. Jamais publiques : elles ne sont lisibles que par un agent
  autorisé, via l'endpoint GET ci-dessous.

AVERTISSEMENT : comme aux étapes précédentes, l'agent est identifié par un
simple agent_id fourni dans la requête. Tant que l'authentification JWT n'est
pas en place, cette protection est provisoire.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.utilisateur import Utilisateur
from app.services.photos import PhotoInvalide, enregistrer_photo, nom_fichier_valide

router = APIRouter(prefix="/photos", tags=["Photos"])

DOSSIER_OBJETS = Path(settings.upload_dir) / "objets"
DOSSIER_PROPRIETAIRES = Path(settings.upload_dir) / "proprietaires"


def _agent(db: Session, agent_id: uuid.UUID) -> Utilisateur:
    agent = db.get(Utilisateur, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent introuvable")
    return agent


async def _lire_et_enregistrer(fichier: UploadFile, dossier: Path) -> str:
    # On lit au plus (limite + 1) octets : si on obtient plus que la limite,
    # le fichier est trop gros, sans jamais charger un fichier énorme en mémoire.
    contenu = await fichier.read(settings.photo_max_octets + 1)
    if len(contenu) > settings.photo_max_octets:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Photo trop lourde (maximum {settings.photo_max_octets // (1024 * 1024)} Mo).",
        )
    try:
        return enregistrer_photo(contenu, dossier, settings.photo_max_cote)
    except PhotoInvalide as erreur:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erreur))


@router.post("/objets", status_code=status.HTTP_201_CREATED)
async def envoyer_photo_objet(agent_id: uuid.UUID, fichier: UploadFile, db: Session = Depends(get_db)):
    """Reçoit la photo d'un objet trouvé. Renvoie l'URL à mettre dans `photo_url`."""
    if not _agent(db, agent_id).droit_enregistrement:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cet agent ne dispose pas du droit d'enregistrement.")
    nom = await _lire_et_enregistrer(fichier, DOSSIER_OBJETS)
    return {"photo_url": f"/fichiers/objets/{nom}"}


@router.post("/proprietaires", status_code=status.HTTP_201_CREATED)
async def envoyer_photo_proprietaire(agent_id: uuid.UUID, fichier: UploadFile, db: Session = Depends(get_db)):
    """Reçoit la photo d'identité du propriétaire lors d'une restitution (privée)."""
    if not _agent(db, agent_id).droit_restitution:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cet agent ne dispose pas du droit de restitution.")
    nom = await _lire_et_enregistrer(fichier, DOSSIER_PROPRIETAIRES)
    return {"photo_url": f"/photos/proprietaires/{nom}"}


@router.get("/proprietaires/{nom}")
def lire_photo_proprietaire(nom: str, agent_id: uuid.UUID, db: Session = Depends(get_db)):
    """Affiche une photo de propriétaire, réservée aux agents de restitution."""
    if not _agent(db, agent_id).droit_restitution:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cet agent ne dispose pas du droit de restitution.")
    if not nom_fichier_valide(nom):  # bloque toute tentative du type ../../.env
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo introuvable")
    chemin = DOSSIER_PROPRIETAIRES / nom
    if not chemin.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo introuvable")
    return FileResponse(chemin, media_type="image/jpeg")
