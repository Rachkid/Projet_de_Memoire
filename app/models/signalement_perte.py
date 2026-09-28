"""
Modèle SignalementPerte : représente une déclaration de perte faite par un
usager avant même qu'un objet ne soit retrouvé, afin de déclencher une
notification automatique en cas de correspondance (cahier des charges,
section 5.1.3).
"""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatutSignalement


class SignalementPerte(Base):
    __tablename__ = "signalements_perte"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )
    usager_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usagers.id"), nullable=False
    )

    categorie: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=True)

    statut: Mapped[str] = mapped_column(
        String(30), nullable=False, default=StatutSignalement.EN_ATTENTE.value
    )

    organisation: Mapped["Organisation"] = relationship(back_populates="signalements")
    usager: Mapped["Usager"] = relationship(back_populates="signalements")

    def __repr__(self) -> str:
        return f"<SignalementPerte {self.categorie} ({self.statut})>"
