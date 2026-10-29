"""
Journal d'audit (étape 16) : écrire « qui a fait quoi, quand ».

La trace est écrite APRÈS l'action elle-même, dans sa propre transaction, et en « meilleur effort » : si le
journal ne peut pas être écrit (base momentanément indisponible), l'action de la personne n'est pas annulée pour
autant, l'erreur est seulement écrite dans les journaux du serveur. Contrepartie à signaler : une action peut,
très rarement, ne laisser aucune trace.

Jamais de mot de passe, de jeton ni de donnée personnelle d'usager dans le journal.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.journal_audit import JournalAudit
from app.models.utilisateur import Utilisateur

journal = logging.getLogger(__name__)

# Actions connues (le texte lisible est donné par la page : voir agent.js).
CONNEXION = "connexion"
CONNEXION_ECHEC = "connexion_echec"
CONNEXION_BLOQUEE = "connexion_bloquee"
MOT_DE_PASSE_CHANGE = "mot_de_passe_change"
MOT_DE_PASSE_REINITIALISE = "mot_de_passe_reinitialise"
COMPTE_CREE = "compte_cree"
COMPTE_MODIFIE = "compte_modifie"
COMPTE_DESACTIVE = "compte_desactive"
COMPTE_REACTIVE = "compte_reactive"
OBJET_ARCHIVE = "objet_archive"
OBJET_ARCHIVE_AUTO = "objet_archive_auto"
OBJET_CORRIGE = "objet_corrige"
OBJET_DESARCHIVE = "objet_desarchive"
DECLARATION_CORRIGEE = "declaration_corrigee"
ORGANISATION_MODIFIEE = "organisation_modifiee"


def tracer(
    db: Session,
    action: str,
    acteur: Utilisateur | None = None,
    organisation_id: uuid.UUID | None = None,
    cible: str | None = None,
    detail: str | None = None,
    adresse: str | None = None,
) -> None:
    try:
        db.add(JournalAudit(
            action=action,
            utilisateur_id=acteur.id if acteur else None,
            organisation_id=organisation_id if organisation_id else (acteur.organisation_id if acteur else None),
            cible=cible[:255] if cible else None,
            detail=detail[:500] if detail else None,
            adresse=adresse[:64] if adresse else None,
        ))
        db.commit()
    except Exception:  # noqa: BLE001 - le journal ne doit jamais faire échouer l'action
        db.rollback()
        journal.exception("Écriture du journal d'audit impossible (action=%s)", action)
