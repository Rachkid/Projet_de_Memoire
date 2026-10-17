"""
Points d'accès d'authentification : connexion et profil de la personne connectée.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.utilisateur import Utilisateur
from app.schemas.auth import Jeton
from app.schemas.utilisateur import ChangementMotDePasse, UtilisateurRead
from app.security import creer_jeton_acces, get_utilisateur_courant, hacher_mot_de_passe, verifier_mot_de_passe

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=Jeton)
def se_connecter(formulaire: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Connexion par identifiant et mot de passe. Le format « formulaire »
    (champs username et password) est le standard OAuth2 : c'est lui qui
    permet au bouton « Authorize » de Swagger de fonctionner.

    Le message d'erreur est volontairement identique que l'identifiant n'existe
    pas ou que le mot de passe soit faux : on ne révèle pas quels identifiants
    existent.
    """
    identifiant = formulaire.username.strip().lower()
    utilisateur = db.query(Utilisateur).filter(Utilisateur.identifiant == identifiant).first()

    mot_de_passe_ok = verifier_mot_de_passe(formulaire.password, utilisateur)
    if not mot_de_passe_ok or not utilisateur.actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Jeton(access_token=creer_jeton_acces(utilisateur))


@router.get("/moi", response_model=UtilisateurRead)
def mon_profil(utilisateur: Utilisateur = Depends(get_utilisateur_courant)):
    """Renvoie le profil de la personne connectée (utile pour vérifier son jeton)."""
    return utilisateur


@router.post("/mot-de-passe")
def changer_mot_de_passe(
    payload: ChangementMotDePasse,
    db: Session = Depends(get_db),
    utilisateur: Utilisateur = Depends(get_utilisateur_courant),
):
    """
    Change le mot de passe de la personne connectée. L'ancien mot de passe est
    exigé : si quelqu'un utilise une session laissée ouverte sur un poste, il
    ne peut pas prendre le contrôle du compte en changeant le mot de passe.
    Erreur 400 (et non 401) en cas d'ancien mot de passe faux : la session
    elle-même reste valable.
    """
    if not verifier_mot_de_passe(payload.ancien_mot_de_passe, utilisateur):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ancien mot de passe incorrect.")
    if payload.nouveau_mot_de_passe == payload.ancien_mot_de_passe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Le nouveau mot de passe doit être différent de l'ancien.")
    utilisateur.mot_de_passe_hash = hacher_mot_de_passe(payload.nouveau_mot_de_passe)
    db.commit()
    return {"message": "Mot de passe modifié."}
