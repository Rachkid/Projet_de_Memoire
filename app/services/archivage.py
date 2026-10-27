"""
Archivage automatique des objets dont le délai de conservation est dépassé (étape 16).

Chaque organisation fixe un « délai de conservation » (90 jours par défaut). Un objet resté EN ATTENTE plus
longtemps n'est plus rendu : il est ARCHIVÉ (retiré des listes, jamais supprimé : sa trace reste). C'est ce que
l'alerte « Bientôt à traiter » annonçait déjà aux administrateurs une semaine à l'avance.

Seuls les objets « en attente » sont concernés : un objet réclamé (quelqu'un vient le chercher) ou restitué
n'est jamais archivé automatiquement.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.enums import StatutObjet
from app.models.objet import Objet
from app.models.organisation import Organisation
from app.services import audit

journal = logging.getLogger(__name__)


def archiver_perimes(db: Session, maintenant: datetime | None = None) -> int:
    """Archive les objets en attente trop anciens. Renvoie le nombre d'objets archivés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    total = 0
    for organisation in db.query(Organisation).all():
        delai = organisation.delai_retention_jours or 90
        limite = maintenant - timedelta(days=delai)
        perimes = (
            db.query(Objet)
            .filter(
                Objet.organisation_id == organisation.id,
                Objet.statut == StatutObjet.EN_ATTENTE.value,
                Objet.date_heure_decouverte < limite,
            )
            .all()
        )
        if not perimes:
            continue
        for objet in perimes:
            objet.statut = StatutObjet.ARCHIVE.value
        db.commit()
        total += len(perimes)
        audit.tracer(
            db,
            audit.OBJET_ARCHIVE_AUTO,
            organisation_id=organisation.id,
            detail=f"{len(perimes)} objet(s) archivé(s) : délai de conservation de {delai} jours dépassé.",
        )
    return total


def _boucle() -> None:
    import time

    while True:
        try:
            with SessionLocal() as db:
                n = archiver_perimes(db)
                if n:
                    journal.info("Archivage automatique : %s objet(s) archivé(s).", n)
        except Exception:  # noqa: BLE001 - la tâche ne doit jamais s'arrêter
            journal.exception("Archivage automatique en erreur")
        time.sleep(max(1, settings.archivage_intervalle_heures) * 3600)


def demarrer_archivage_automatique() -> None:
    """Lance la vérification au démarrage puis toutes les « archivage_intervalle_heures » heures."""
    if not settings.archivage_auto:
        journal.info("Archivage automatique désactivé (ARCHIVAGE_AUTO=false).")
        return
    threading.Thread(target=_boucle, name="archivage-auto", daemon=True).start()
