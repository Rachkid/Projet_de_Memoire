"""
Modèle Usager : représente une personne extérieure au système (élève,
étudiant, enseignant, voyageur) qui signale une perte ou récupère un objet.

Contrairement à Utilisateur, ce modèle ne porte aucun droit d'accès ni
mot de passe : son seul rôle est de relier, via un identifiant simple
(le numéro de téléphone), les différents signalements et restitutions
d'une même personne dans le temps (mémoire, chapitre 3, section 3.2.2).
"""

import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Usager(Base):
    __tablename__ = "usagers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identifiant simple d'une personne : pas de mot de passe, pas de connexion.
    telephone: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(150), nullable=True)

    signalements: Mapped[list["SignalementPerte"]] = relationship(back_populates="usager")
    restitutions: Mapped[list["Restitution"]] = relationship(back_populates="usager")

    def __repr__(self) -> str:
        return f"<Usager {self.telephone}>"
