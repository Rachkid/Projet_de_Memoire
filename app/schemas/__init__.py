"""
Rassemble tous les schémas du projet en un seul endroit, pour pouvoir écrire
par exemple `from app.schemas import ObjetCreate` ailleurs dans le code.
"""

from app.schemas.organisation import OrganisationCreate, OrganisationRead
from app.schemas.utilisateur import UtilisateurCreate, UtilisateurRead
from app.schemas.usager import UsagerCreate, UsagerRead
from app.schemas.objet import ObjetCreate, ObjetRead
from app.schemas.restitution import RestitutionCreate, RestitutionRead
from app.schemas.signalement_perte import SignalementPerteCreate, SignalementPerteRead

__all__ = [
    "OrganisationCreate", "OrganisationRead",
    "UtilisateurCreate", "UtilisateurRead",
    "UsagerCreate", "UsagerRead",
    "ObjetCreate", "ObjetRead",
    "RestitutionCreate", "RestitutionRead",
    "SignalementPerteCreate", "SignalementPerteRead",
]
