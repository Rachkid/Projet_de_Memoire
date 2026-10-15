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

Accès : l'envoi exige d'être connecté avec le droit correspondant
(enregistrement pour les photos d'objets, restitution pour celles de
propriétaires). Les photos de propriétaires sont rangées dans un sous-dossier
PAR ORGANISATION : un agent ne peut jamais lire celles d'une autre organisation.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.config import settings
from app.models.utilisateur import Utilisateur
from app.security import exiger_enregistrement, exiger_restitution
from app.services.photos import PhotoInvalide, enregistrer_photo, nom_fichier_valide

router = APIRouter(prefix="/photos", tags=["Photos"])

DOSSIER_OBJETS = Path(settings.upload_dir) / "objets"
DOSSIER_PROPRIETAIRES = Path(settings.upload_dir) / "proprietaires"


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
async def envoyer_photo_objet(fichier: UploadFile, agent: Utilisateur = Depends(exiger_enregistrement)):
    """Reçoit la photo d'un objet trouvé. Renvoie l'URL à mettre dans `photo_url`."""
    nom = await _lire_et_enregistrer(fichier, DOSSIER_OBJETS)
    return {"photo_url": f"/fichiers/objets/{nom}"}


def _dossier_proprietaires(agent: Utilisateur) -> Path:
    """Sous-dossier privé de l'organisation de l'agent (isolation multi-tenant)."""
    return DOSSIER_PROPRIETAIRES / str(agent.organisation_id)


@router.post("/proprietaires", status_code=status.HTTP_201_CREATED)
async def envoyer_photo_proprietaire(fichier: UploadFile, agent: Utilisateur = Depends(exiger_restitution)):
    """Reçoit la photo d'identité du propriétaire lors d'une restitution (privée)."""
    nom = await _lire_et_enregistrer(fichier, _dossier_proprietaires(agent))
    return {"photo_url": f"/photos/proprietaires/{nom}"}


@router.get("/proprietaires/{nom}")
def lire_photo_proprietaire(nom: str, agent: Utilisateur = Depends(exiger_restitution)):
    """
    Affiche une photo de propriétaire, réservée aux agents de restitution de la
    même organisation. Attention : un navigateur ne peut pas envoyer le jeton en
    ouvrant simplement l'adresse ; on teste donc cette route depuis Swagger (/docs).
    """
    if not nom_fichier_valide(nom):  # bloque toute tentative du type ../../.env
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo introuvable")
    chemin = _dossier_proprietaires(agent) / nom  # uniquement dans le dossier de SON organisation
    if not chemin.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo introuvable")
    return FileResponse(chemin, media_type="image/jpeg")
