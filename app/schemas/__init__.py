"""
Rassemble tous les schémas du projet en un seul endroit, pour pouvoir écrire
par exemple `from app.schemas import ObjetCreate` ailleurs dans le code.
"""

from app.schemas.organisation import OrganisationCreate, OrganisationRead, OrganisationUpdate, ThemeRead
from app.schemas.utilisateur import (
    ChangementMotDePasse,
    ReinitialisationMotDePasse,
    UtilisateurCreate,
    UtilisateurRead,
    UtilisateurUpdate,
)
from app.schemas.usager import UsagerCreate, UsagerRead
from app.schemas.objet import ObjetCreate, ObjetRead, ObjetUpdate
from app.schemas.restitution import RestitutionCreate, RestitutionRead
from app.schemas.signalement_perte import SignalementPerteCreate, SignalementPerteRead

__all__ = [
    "OrganisationCreate", "OrganisationRead", "OrganisationUpdate", "ThemeRead",
    "UtilisateurCreate", "UtilisateurRead", "UtilisateurUpdate", "ChangementMotDePasse",
    "ReinitialisationMotDePasse",
    "UsagerCreate", "UsagerRead",
    "ObjetCreate", "ObjetRead", "ObjetUpdate",
    "RestitutionCreate", "RestitutionRead",
    "SignalementPerteCreate", "SignalementPerteRead",
]
