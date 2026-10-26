"""
Alertes de la cloche (étape 15 bis) : ce qui demande l'attention de la personne connectée.
Calculées à la demande, limitées à son organisation. Aucune donnée personnelle : seulement des totaux.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.utilisateur import Utilisateur
from app.security import get_utilisateur_courant
from app.services.alertes import alertes_pour

router = APIRouter(prefix="/alertes", tags=["Alertes"])


@router.get("/")
def mes_alertes(db: Session = Depends(get_db), personnel: Utilisateur = Depends(get_utilisateur_courant)):
    """Alertes de mon organisation, adaptées à mon rôle (les administrateurs en voient davantage)."""
    liste = alertes_pour(db, personnel)
    return {"total": sum(a["nombre"] for a in liste), "alertes": liste}
