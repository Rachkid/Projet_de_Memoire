"""
Ce fichier importe tous les modèles du projet en un seul endroit.

C'est important pour deux raisons : d'une part, cela permet d'écrire
`from app.models import Objet` ailleurs dans le code plutôt que le
chemin complet `from app.models.objet import Objet` ; d'autre part,
et surtout, cela garantit que toutes les classes sont bien enregistrées
auprès de SQLAlchemy avant que les relations entre elles (qui utilisent
des noms sous forme de texte, ex. "Utilisateur") ne soient résolues.
"""

from app.models.organisation import Organisation
from app.models.utilisateur import Utilisateur
from app.models.usager import Usager
from app.models.objet import Objet
from app.models.restitution import Restitution
from app.models.signalement_perte import SignalementPerte

__all__ = [
    "Organisation",
    "Utilisateur",
    "Usager",
    "Objet",
    "Restitution",
    "SignalementPerte",
]
