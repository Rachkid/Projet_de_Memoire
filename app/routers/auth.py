"""
Points d'accès d'authentification : connexion et profil de la personne connectée.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.limites import adresse_client, echecs_connexion, echecs_connexion_adresse, trop_de_tentatives
from app.models.utilisateur import Utilisateur
from app.schemas.auth import Jeton
from app.schemas.utilisateur import ChangementMotDePasse, UtilisateurRead
from app.security import (
    creer_jeton_acces,
    get_utilisateur_courant_libre,
    hacher_mot_de_passe,
    verifier_mot_de_passe,
)
from app.services import audit

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=Jeton)
def se_connecter(requete: Request, formulaire: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Connexion par identifiant et mot de passe. Le format « formulaire »
    (champs username et password) est le standard OAuth2 : c'est lui qui
    permet au bouton « Authorize » de Swagger de fonctionner.

    Le message d'erreur est volontairement identique que l'identifiant n'existe
    pas ou que le mot de passe soit faux : on ne révèle pas quels identifiants
    existent.

    Étape 16 : après trop d'échecs (voir config.py), l'accès est bloqué quelques minutes — même avec le bon
    mot de passe, pour que l'on ne puisse pas deviner le bon par essais successifs. Le blocage vise une
    adresse (ou un couple adresse + identifiant) : il ne permet pas de verrouiller le compte de quelqu'un d'autre.
    """
    identifiant = formulaire.username.strip().lower()
    adresse = adresse_client(requete)
    cle_couple = f"{adresse}|{identifiant}"
    attente = max(echecs_connexion.attente(cle_couple), echecs_connexion_adresse.attente(adresse))
    if attente:
        audit.tracer(db, audit.CONNEXION_BLOQUEE, adresse=adresse, detail="Connexion refusée : trop de tentatives.")
        raise trop_de_tentatives(attente)
    utilisateur = db.query(Utilisateur).filter(Utilisateur.identifiant == identifiant).first()

    mot_de_passe_ok = verifier_mot_de_passe(formulaire.password, utilisateur)
    if not mot_de_passe_ok or not utilisateur.actif:
        echecs_connexion.enregistrer(cle_couple)
        echecs_connexion_adresse.enregistrer(adresse)
        # L'identifiant n'est noté que s'il existe : on évite de garder un mot de passe tapé par erreur dans ce champ.
        audit.tracer(
            db, audit.CONNEXION_ECHEC, acteur=utilisateur, cible=utilisateur.identifiant if utilisateur else None,
            adresse=adresse, detail="Mot de passe incorrect." if utilisateur and utilisateur.actif else "Identifiant inconnu ou compte désactivé.",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    echecs_connexion.oublier(cle_couple)  # connexion réussie : le compteur de ce couple repart de zéro
    audit.tracer(db, audit.CONNEXION, acteur=utilisateur, cible=utilisateur.identifiant, adresse=adresse)
    return Jeton(access_token=creer_jeton_acces(utilisateur), doit_changer_mot_de_passe=utilisateur.doit_changer_mot_de_passe)


@router.get("/moi", response_model=UtilisateurRead)
def mon_profil(utilisateur: Utilisateur = Depends(get_utilisateur_courant_libre)):
    """Renvoie le profil de la personne connectée (utile pour vérifier son jeton)."""
    return utilisateur


@router.post("/mot-de-passe")
def changer_mot_de_passe(
    requete: Request,
    payload: ChangementMotDePasse,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_courant_libre),
):
    """
    Change le mot de passe de la personne connectée. L'ancien mot de passe est
    exigé : si quelqu'un utilise une session laissée ouverte sur un poste, il
    ne peut pas prendre le contrôle du compte en changeant le mot de passe.
    Erreur 400 (et non 401) en cas d'ancien mot de passe faux : la session
    elle-même reste valable.

    Étape 16 : le changement met fin à TOUTES les sessions ouvertes de ce compte (autre téléphone, poste
    oublié) ; la réponse contient un nouveau jeton pour que la personne reste connectée ici. Le mot de passe
    n'est plus provisoire. Les essais d'ancien mot de passe sont limités comme à la connexion.
    """
    cle = f"mdp|{utilisateur.id}"
    attente = echecs_connexion.attente(cle)
    if attente:
        raise trop_de_tentatives(attente)
    if not verifier_mot_de_passe(payload.ancien_mot_de_passe, utilisateur):
        echecs_connexion.enregistrer(cle)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ancien mot de passe incorrect.")
    if payload.nouveau_mot_de_passe == payload.ancien_mot_de_passe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nouveau mot de passe doit être différent de l'ancien.")
    echecs_connexion.oublier(cle)
    utilisateur.mot_de_passe_hash = hacher_mot_de_passe(payload.nouveau_mot_de_passe)
    utilisateur.version_session = (utilisateur.version_session or 0) + 1
    utilisateur.doit_changer_mot_de_passe = False
    db.commit()
    audit.tracer(db, audit.MOT_DE_PASSE_CHANGE, acteur=utilisateur, cible=utilisateur.identifiant, adresse=adresse_client(requete))
    return {"message": "Mot de passe modifié.", "access_token": creer_jeton_acces(utilisateur), "token_type": "bearer"}
