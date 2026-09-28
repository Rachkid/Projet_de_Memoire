"""
Modèle Objet : représente un objet trouvé, avec toutes les informations
définies dans le cahier des charges (section 5.1.1) et ses déclinaisons par
secteur (sections 5.2 et 5.3) : catégorie, photo, lieu, moment de la
découverte, code QR, et statut du cycle de vie de l'objet.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import StatutObjet


class Objet(Base):
    __tablename__ = "objets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )
    # L'agent qui a procédé à l'enregistrement (traçabilité, chapitre 2, section 2.2)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("utilisateurs.id"), nullable=False
    )

    categorie: Mapped[str] = mapped_column(String(80), nullable=False)
    photo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    date_heure_decouverte: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # "vehicule" ou "locaux" pour le secteur transport ; simple précision de
    # bâtiment pour le secteur éducation (cahier des charges, sections 5.2 et 5.3).
    type_emplacement: Mapped[str] = mapped_column(String(30), nullable=True)
    lieu_detail: Mapped[str] = mapped_column(String(255), nullable=True)

    # Identifiant unique généré à l'enregistrement, utilisé pour l'étiquetage
    # physique de l'objet (cahier des charges, section 5.1.1).
    qr_code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    statut: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StatutObjet.EN_ATTENTE.value
    )

    organisation: Mapped["Organisation"] = relationship(back_populates="objets")
    agent_enregistrement: Mapped["Utilisateur"] = relationship(back_populates="objets_enregistres")

    # Un objet donne lieu à au plus une restitution (relation "0..1" du
    # chapitre 3, section 3.2.2) : uselist=False en fait une relation
    # un-à-un plutôt qu'un-à-plusieurs du point de vue de Objet.
    restitution: Mapped["Restitution | None"] = relationship(back_populates="objet", uselist=False)

    def __repr__(self) -> str:
        return f"<Objet {self.categorie} ({self.statut})>"
