"""
Modèle Restitution : représente le dossier de remise d'un objet à son
propriétaire, incluant la vérification de la pièce d'identité et la photo
prise à des fins de traçabilité (cahier des charges, section 5.1.4).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Restitution(Base):
    __tablename__ = "restitutions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    objet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("objets.id"), unique=True, nullable=False
    )
    # L'agent qui a validé la restitution (traçabilité, chapitre 2, section 2.2)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id"), nullable=False
    )
    # La personne qui récupère l'objet (peut être null tant que le dossier
    # n'a pas encore identifié formellement l'usager)
    usager_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usagers.id"), nullable=True
    )

    type_piece_identite: Mapped[str] = mapped_column(String(50), nullable=True)
    numero_piece: Mapped[str] = mapped_column(String(50), nullable=True)
    photo_proprietaire_url: Mapped[str] = mapped_column(String(500), nullable=True)
    date_heure: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Résultat du contrôle anti-fraude par détail caché (cahier des charges,
    # section 5.1.4, point 2) : conditionne toute la suite du processus.
    detail_controle_valide: Mapped[bool] = mapped_column(Boolean, default=False)

    objet: Mapped["Objet"] = relationship(back_populates="restitution")
    agent_restitution: Mapped["Utilisateur"] = relationship(back_populates="restitutions_validees")
    usager: Mapped["Usager | None"] = relationship(back_populates="restitutions")

    def __repr__(self) -> str:
        return f"<Restitution objet={self.objet_id} valide={self.detail_controle_valide}>"
