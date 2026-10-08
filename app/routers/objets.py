"""
Points d'accès de l'API pour la ressource Objet : le cœur fonctionnel du
système (cahier des charges, section 5.1.1 ; mémoire, chapitre 2, section 2.3.1,
cas d'utilisation "Enregistrer un objet trouvé").
"""

import uuid
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.objet import Objet
from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.schemas.objet import ObjetCreate, ObjetRead

router = APIRouter(prefix="/objets", tags=["Objets"])


def generer_code_qr() -> str:
    """
    Génère un identifiant court et unique pour un objet, qui servira de
    contenu au code QR imprimé sur son étiquette physique (cahier des
    charges, section 5.1.1). On utilise une valeur aléatoire plutôt qu'un
    simple numéro croissant (1, 2, 3...), pour qu'il soit impossible de
    deviner le code d'un autre objet en essayant des numéros voisins.
    """
    return f"OBJ-{uuid.uuid4().hex[:10].upper()}"


@router.post("/", response_model=ObjetRead, status_code=status.HTTP_201_CREATED)
def enregistrer_objet(payload: ObjetCreate, db: Session = Depends(get_db)):
    """
    Enregistre un nouvel objet trouvé. Avant toute création, on vérifie que
    l'organisation et l'agent indiqués existent réellement, et que l'agent
    dispose bien du droit d'enregistrement (mémoire, chapitre 2, section 2.2) :
    mieux vaut un message d'erreur clair ici qu'une erreur technique obscure
    renvoyée directement par la base de données.
    """
    organisation = db.get(Organisation, payload.organisation_id)
    if organisation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organisation introuvable")

    agent = db.get(Utilisateur, payload.agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent introuvable")
    if not agent.droit_enregistrement:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cet agent ne dispose pas du droit d'enregistrement.",
        )

    objet = Objet(**payload.model_dump(), qr_code=generer_code_qr())
    db.add(objet)
    db.commit()
    db.refresh(objet)
    return objet


@router.get("/", response_model=list[ObjetRead])
def lister_objets(organisation_id: uuid.UUID | None = None, db: Session = Depends(get_db)):
    """
    Liste les objets enregistrés. Le filtre organisation_id est essentiel :
    c'est lui qui garantit, au niveau de l'API, qu'un usager consultant
    l'écran d'affichage ou le portail d'une organisation ne voit jamais les
    objets d'une autre organisation (isolation multi-tenant, chapitre 3,
    section 3.1 ; maquettes, sections 3.4.2 et 3.4.3).
    """
    requete = db.query(Objet)
    if organisation_id is not None:
        requete = requete.filter(Objet.organisation_id == organisation_id)
    return requete.order_by(Objet.date_heure_decouverte.desc()).all()


@router.get("/{objet_id}", response_model=ObjetRead)
def obtenir_objet(objet_id: uuid.UUID, db: Session = Depends(get_db)):
    """Récupère un objet précis à partir de son identifiant."""
    objet = db.get(Objet, objet_id)
    if objet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    return objet


@router.get("/{objet_id}/qrcode")
def obtenir_image_qrcode(objet_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Génère et renvoie l'image du code QR d'un objet, prête à être imprimée
    sur une étiquette. L'image est produite à la volée (jamais stockée sur
    le disque), à partir du code texte déjà enregistré pour cet objet.
    """
    objet = db.get(Objet, objet_id)
    if objet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")

    image = qrcode.make(objet.qr_code)
    tampon = BytesIO()
    image.save(tampon, format="PNG")
    tampon.seek(0)
    return StreamingResponse(tampon, media_type="image/png")
