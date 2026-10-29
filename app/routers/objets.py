"""
Points d'accès de l'API pour la ressource Objet : le cœur fonctionnel du
système (cahier des charges, section 5.1.1 ; mémoire, chapitre 2, section 2.3.1,
cas d'utilisation "Enregistrer un objet trouvé").
"""

import uuid
from datetime import datetime, timezone
from io import BytesIO

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.objet import Objet
from app.models.utilisateur import Utilisateur
from app.models.enums import StatutObjet
from app.schemas.signalement_perte import SignalementPersonnelRead
from app.schemas.objet import ObjetCreate, ObjetCreeRead, ObjetRead, ObjetUpdate
from app.security import exiger_administrateur, exiger_enregistrement, exiger_enregistrement_ou_administrateur, get_utilisateur_courant
from app.services import audit
from app.services.rapprochement import signalements_correspondants, traiter_nouvel_objet

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


@router.post("/", response_model=ObjetCreeRead, status_code=status.HTTP_201_CREATED)
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
    nombre = traiter_nouvel_objet(db, objet)
    # On renvoie l'objet créé, plus le nombre de personnes déjà en attente d'un objet de ce type :
    # l'agent voit tout de suite que son enregistrement a servi.
    return ObjetCreeRead.model_validate(objet).model_copy(update={"signalements_correspondants": nombre})


@router.get("/", response_model=list[ObjetRead])
def lister_objets(
    statut: StatutObjet | None = None,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """
    Liste les objets de l'organisation de la personne connectée (Étape 12).

    Avant l'Étape 12 cette liste était publique et acceptait un filtre organisation_id : n'importe
    qui pouvait donc la lire, y compris quand l'organisation avait désactivé la consultation à
    distance. Elle est maintenant réservée au personnel connecté et limitée à SON organisation ;
    le public passe par /portail/{identifiant}/objets, qui n'expose que le strict nécessaire.

    Sans filtre, les objets archivés (saisie erronée, objet détruit...) sont retirés de la liste.
    Avec ?statut=..., on obtient les objets de ce statut (y compris « archive »).
    """
    requete = db.query(Objet).filter(Objet.organisation_id == personnel.organisation_id)
    if statut is not None:
        requete = requete.filter(Objet.statut == statut.value)
    else:
        requete = requete.filter(Objet.statut != StatutObjet.ARCHIVE.value)
    return requete.order_by(Objet.date_heure_decouverte.desc()).all()


def _objet_de_mon_organisation(db: Session, objet_id: uuid.UUID, personnel: Utilisateur) -> Objet:
    """Un objet d'une autre organisation « n'existe pas » (404) : on ne révèle même pas son existence."""
    objet = db.get(Objet, objet_id)
    if objet is None or objet.organisation_id != personnel.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    return objet


@router.get("/{objet_id}", response_model=ObjetRead)
def obtenir_objet(
    objet_id: uuid.UUID,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """Récupère un objet précis de l'organisation de la personne connectée."""
    return _objet_de_mon_organisation(db, objet_id, personnel)


@router.get("/{objet_id}/signalements", response_model=list[SignalementPersonnelRead])
def signalements_de_cet_objet(
    objet_id: uuid.UUID,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """
    Les personnes qui ont déclaré la perte d'un objet semblable à celui-ci (même catégorie, dates
    compatibles), avec leur nom et leur téléphone : ce sont elles que l'agent attend au guichet.
    """
    objet = _objet_de_mon_organisation(db, objet_id, personnel)
    return [SignalementPersonnelRead.depuis_signalement(s) for s in signalements_correspondants(db, objet)]


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
    agent: Utilisateur = Depends(exiger_enregistrement_ou_administrateur),
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
    # Le détail secret n'est jamais écrit dans le journal : on indique seulement qu'il a changé.
    audit.tracer(db, audit.OBJET_CORRIGE, acteur=agent, organisation_id=objet.organisation_id, cible=objet.qr_code,
                 detail="Champs modifiés : " + ", ".join(sorted(modifications)))
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
    audit.tracer(db, audit.OBJET_ARCHIVE, acteur=utilisateur, organisation_id=objet.organisation_id,
                 cible=objet.qr_code, detail=f"Catégorie : {objet.categorie}")
    return objet


@router.patch("/{objet_id}/desarchiver", response_model=ObjetRead)
def desarchiver_objet(
    objet_id: uuid.UUID,
    db: Session = Depends(get_db),
    administrateur: Utilisateur = Depends(exiger_administrateur),
):
    """
    Remet en attente un objet archivé (archivage fait par erreur, ou objet réclamé après coup).
    Réservé aux administrateurs. Le délai de conservation repart d'aujourd'hui : sans cela, un objet
    archivé automatiquement parce que son délai était dépassé serait archivé de nouveau aussitôt.
    """
    objet = db.get(Objet, objet_id)
    if objet is None or objet.organisation_id != administrateur.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")
    if objet.statut != StatutObjet.ARCHIVE.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cet objet n'est pas archivé.")
    objet.statut = StatutObjet.EN_ATTENTE.value
    objet.retention_depuis = datetime.now(timezone.utc)
    db.commit()
    db.refresh(objet)
    traiter_nouvel_objet(db, objet)  # des déclarations ont pu être déposées entre-temps
    audit.tracer(db, audit.OBJET_DESARCHIVE, acteur=administrateur, organisation_id=objet.organisation_id,
                 cible=objet.qr_code, detail=f"Catégorie : {objet.categorie}")
    return objet


@router.get("/{objet_id}/qrcode")
def obtenir_image_qrcode(
    objet_id: uuid.UUID,
    db: Session = Depends(get_db),
    personnel: Utilisateur = Depends(get_utilisateur_courant),
):
    """
    Génère et renvoie l'image du code QR d'un objet, prête à être imprimée
    sur une étiquette. L'image est produite à la volée (jamais stockée sur
    le disque), à partir du code texte déjà enregistré pour cet objet.
    """
    objet = _objet_de_mon_organisation(db, objet_id, personnel)

    image = qrcode.make(objet.qr_code)
    tampon = BytesIO()
    image.save(tampon, format="PNG")
    tampon.seek(0)
    return StreamingResponse(tampon, media_type="image/png")
