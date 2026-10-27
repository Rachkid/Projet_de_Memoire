"""
Modèle JournalAudit (étape 16) : la trace des actions sensibles (connexions, comptes, mots de passe, archivages).

Une ligne n'est JAMAIS modifiée ni supprimée par l'application : le journal sert à répondre à « qui a fait quoi,
et quand ? ». Il ne contient aucun mot de passe, ni jeton, ni donnée personnelle des usagers.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class JournalAudit(Base):
    __tablename__ = "journal_audit"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date_heure: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, index=True, nullable=False)

    # Organisation concernée (vide pour une tentative de connexion sur un identifiant inconnu).
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    # Personne qui a agi (vide si inconnue : échec de connexion, tâche automatique).
    utilisateur_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    action: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    cible: Mapped[str | None] = mapped_column(String(255), nullable=True)   # ex. identifiant du compte touché
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(64), nullable=True)  # adresse réseau de l'appelant
