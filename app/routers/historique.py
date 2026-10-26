"""
Historique (Étape 14), réservé aux administrateurs et limité à leur organisation :
- journal des remises (qui a remis quoi, à qui, quand), filtrable ;
- frise d'un objet (de sa découverte à son issue) ;
- historique d'une personne, retrouvée par son numéro de téléphone.

Le numéro de pièce d'identité n'est jamais renvoyé en entier : seuls les
derniers caractères le sont, pour pouvoir recouper sans exposer le document.
"""

import re
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.objet import Objet
from app.models.restitution import Restitution
from app.models.signalement_perte import SignalementPerte
from app.models.usager import Usager
from app.models.utilisateur import Utilisateur
from app.security import exiger_administrateur

router = APIRouter(prefix="/historique", tags=["Historique"])

FUSEAU = timezone(timedelta(hours=1))  # Niger : UTC+1, sans heure d'été
LIMITE = 500


def _masquer(numero: Optional[str]) -> Optional[str]:
    if not numero:
        return None
    return ("•" * max(len(numero) - 3, 0)) + numero[-3:]


def _debut_du_jour(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=FUSEAU).astimezone(timezone.utc)


def _ligne_remise(r: Restitution, objet: Objet, agent: Utilisateur, usager: Optional[Usager]) -> dict:
    return {
        "id": str(r.id),
        "date_heure": r.date_heure,
        "objet_id": str(objet.id),
        "categorie": objet.categorie,
        "photo_url": objet.photo_url,
        "agent_id": str(agent.id),
        "agent_nom": agent.nom,
        "usager_nom": usager.nom if usager else None,
        "usager_telephone": usager.telephone if usager else None,
        "type_piece": r.type_piece_identite,
        "numero_piece_masque": _masquer(r.numero_piece),
    }


@router.get("/remises")
def journal_des_remises(
    du: Optional[date] = None,
    au: Optional[date] = None,
    agent_id: Optional[uuid.UUID] = None,
    q: Optional[str] = Query(None, max_length=100, description="Texte cherché dans la catégorie, le nom ou le téléphone"),
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_administrateur),
):
    """Remises de mon organisation, les plus récentes d'abord (500 au maximum)."""
    requete = (
        db.query(Restitution, Objet, Utilisateur, Usager)
        .select_from(Restitution)
        .join(Objet, Objet.id == Restitution.objet_id)
        .join(Utilisateur, Utilisateur.id == Restitution.agent_id)
        .outerjoin(Usager, Usager.id == Restitution.usager_id)
        .filter(Objet.organisation_id == admin.organisation_id)
    )
    if du:
        requete = requete.filter(Restitution.date_heure >= _debut_du_jour(du))
    if au:
        requete = requete.filter(Restitution.date_heure < _debut_du_jour(au + timedelta(days=1)))
    if agent_id:
        requete = requete.filter(Restitution.agent_id == agent_id)
    lignes = requete.order_by(Restitution.date_heure.desc()).limit(LIMITE).all()

    resultat = [_ligne_remise(r, o, a, u) for r, o, a, u in lignes]
    if q and q.strip():
        mot = q.strip().lower()
        chiffres = re.sub(r"\D", "", mot)
        def correspond(l: dict) -> bool:
            texte = " ".join(str(l[c] or "") for c in ("categorie", "usager_nom", "agent_nom")).lower()
            tel = re.sub(r"\D", "", l["usager_telephone"] or "")
            return mot in texte or (len(chiffres) >= 3 and chiffres in tel)
        resultat = [l for l in resultat if correspond(l)]
    return resultat


@router.get("/agents")
def agents_de_mon_organisation(db: Session = Depends(get_db), admin: Utilisateur = Depends(exiger_administrateur)):
    """Liste courte (id, nom) pour le filtre « par agent » du journal."""
    comptes = db.query(Utilisateur).filter(Utilisateur.organisation_id == admin.organisation_id).order_by(Utilisateur.nom).all()
    return [{"id": str(c.id), "nom": c.nom} for c in comptes]


@router.get("/objets/{objet_id}")
def frise_d_un_objet(objet_id: uuid.UUID, db: Session = Depends(get_db), admin: Utilisateur = Depends(exiger_administrateur)):
    """Les étapes de la vie d'un objet : trouvé, puis remis (s'il l'a été)."""
    objet = db.get(Objet, objet_id)
    if objet is None or objet.organisation_id != admin.organisation_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objet introuvable")

    etapes = []
    enregistreur = db.get(Utilisateur, objet.agent_id)
    etapes.append({
        "type": "trouve",
        "date_heure": objet.date_heure_decouverte,
        "titre": "Objet trouvé et enregistré",
        "acteur": enregistreur.nom if enregistreur else None,
        "detail": objet.lieu_detail,
    })
    restitution = db.query(Restitution).filter(Restitution.objet_id == objet.id).first()
    if restitution:
        agent = db.get(Utilisateur, restitution.agent_id)
        usager = db.get(Usager, restitution.usager_id) if restitution.usager_id else None
        etapes.append({
            "type": "restitue",
            "date_heure": restitution.date_heure,
            "titre": "Remis à son propriétaire",
            "acteur": agent.nom if agent else None,
            "detail": " — ".join(x for x in (
                usager.nom if usager and usager.nom else None,
                usager.telephone if usager else None,
                restitution.type_piece_identite,
            ) if x),
        })
    return {"objet_id": str(objet.id), "statut": objet.statut, "etapes": etapes}


@router.get("/personnes")
def historique_d_une_personne(
    telephone: str = Query(..., min_length=6, max_length=30),
    db: Session = Depends(get_db),
    admin: Utilisateur = Depends(exiger_administrateur),
):
    """Déclarations et remises d'une personne, dans mon organisation uniquement."""
    chiffres = re.sub(r"\D", "", telephone)
    usagers = [u for u in db.query(Usager).all() if chiffres and re.sub(r"\D", "", u.telephone).endswith(chiffres[-8:])]
    if not usagers:
        return {"trouve": False, "personne": None, "declarations": [], "remises": []}
    ids = [u.id for u in usagers]
    usager = usagers[0]

    declarations = (
        db.query(SignalementPerte)
        .filter(SignalementPerte.organisation_id == admin.organisation_id, SignalementPerte.usager_id.in_(ids))
        .all()
    )
    remises = (
        db.query(Restitution, Objet, Utilisateur, Usager)
        .select_from(Restitution)
        .join(Objet, Objet.id == Restitution.objet_id)
        .join(Utilisateur, Utilisateur.id == Restitution.agent_id)
        .outerjoin(Usager, Usager.id == Restitution.usager_id)
        .filter(Objet.organisation_id == admin.organisation_id, Restitution.usager_id.in_(ids))
        .order_by(Restitution.date_heure.desc())
        .all()
    )
    return {
        "trouve": True,
        "personne": {"nom": next((u.nom for u in usagers if u.nom), None), "telephone": usager.telephone},
        "declarations": [
            {"id": str(s.id), "categorie": s.categorie, "description": s.description,
             "date_perte": s.date_perte, "lieu_approximatif": s.lieu_approximatif, "statut": s.statut}
            for s in declarations
        ],
        "remises": [_ligne_remise(r, o, a, u) for r, o, a, u in remises],
    }
