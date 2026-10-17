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
from app.models.utilisateur import Utilisateur
from app.models.enums import StatutObjet
from app.schemas.objet import ObjetCreate, ObjetRead, ObjetUpdate
from app.security import exiger_enregistrement, exiger_enregistrement_ou_administrateur
from app.services.rapprochement import traiter_nouvel_objet

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
def enregistrer_objet(
    payload: ObjetCreate,
    db: Session = Depends(get_db),
    agent: Utilisateur = Depends(exiger_enregistrement),
):
    """
    Enregistre un nouvel objet trouvé. L'agent et son organisation viennent du
    jeton de connexion : il est impossible d'enregistrer un objet au nom d'un
    autre agent ou dans une autre organisation. Le droit d'enregistrement est
    vérifié par la dépendance exiger_enregistrement (403 sinon).
    """
    objet = Objet(
        **payload.model_dump(),
        organisation_id=agent.organisation_id,
        agent_id=agent.id,
        qr_code=generer_code_qr(),
    )
    db.add(objet)
    db.commit()
    db.refresh(objet)

    # Rapprochement automatique : des usagers ont-ils déjà signalé la perte
    # d'un objet de ce type ? Si oui, ils sont marqués et prévenus.
    traiter_nouvel_objet(db, objet)
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
    # Les objets archivés (saisie erronée, objet détruit...) sont retirés des listes.
    requete = db.query(Objet).filter(Objet.statut != StatutObjet.ARCHIVE.value)
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


def _objet_modifiable(db: Session, objet_id: uuid.UUID, utilisateur: Utilisateur) -> Objet:
    """
    Charge un objet de l'organisation de la personne connectée. Un objet d'une
    autre organisation « n'existe pas » (404). Un objet déjà restitué ou
    archivé n'est plus modifiable (409) : son dossier est clos et doit rester
    tel qu'il était au moment de la remise.
    """
    objet = db.get(Objet, objet_id)
    if objet is None or objet.organisation_id != utilisateur.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    if objet.statut in (StatutObjet.RESTITUE.value, StatutObjet.ARCHIVE.value):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet objet est déjà restitué ou archivé : il n'est plus modifiable.")
    return objet


@router.patch("/{objet_id}", response_model=ObjetRead)
def corriger_objet(
    objet_id: uuid.UUID,
    payload: ObjetUpdate,
    db: Session = Depends(get_db),
    agent: Utilisateur = Depends(exiger_enregistrement),
):
    """
    Corrige un objet (erreur de saisie). PATCH = modification partielle : seuls
    les champs envoyés changent. Si la catégorie ou la date change, le
    rapprochement avec les signalements est relancé.
    """
    objet = _objet_modifiable(db, objet_id, agent)
    modifications = payload.model_dump(exclude_unset=True)
    if not modifications:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Aucune modification fournie.")
    for champ, valeur in modifications.items():
        setattr(objet, champ, valeur)
    db.commit()
    db.refresh(objet)
    if "categorie" in modifications or "date_heure_decouverte" in modifications:
        traiter_nouvel_objet(db, objet)
    return objet


@router.patch("/{objet_id}/archiver", response_model=ObjetRead)
def archiver_objet(
    objet_id: uuid.UUID,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(exiger_enregistrement_ou_administrateur),
):
    """
    Retire un objet des listes (saisie erronée, objet détruit ou donné...) SANS
    le supprimer : la trace de son enregistrement est conservée.
    """
    objet = _objet_modifiable(db, objet_id, utilisateur)
    objet.statut = StatutObjet.ARCHIVE.value
    db.commit()
    db.refresh(objet)
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
