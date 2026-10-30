"""
Modèle CategoriePersonnalisee (étape 19) : une catégorie d'objet ajoutée par l'administrateur d'une organisation,
en plus de la liste standard (voir services/categories.py).

- « nom » : le nom saisi (en français), qui est aussi la valeur enregistrée sur les objets et les déclarations ;
- « nom_cle » : le même nom sans accents ni majuscules, pour interdire les doublons ;
- « icone » : le nom d'une icône du catalogue de l'application (jamais un fichier envoyé) ;
- « traductions » : texte JSON {"en": ..., "ha": ..., "dje": ..., "ar": ...}, toutes les langues étant facultatives ;
- « actif » : une catégorie n'est jamais supprimée (des objets l'utilisent) : on la désactive.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class CategoriePersonnalisee(Base):
    __tablename__ = "categories_personnalisees"
    __table_args__ = (UniqueConstraint("organisation_id", "nom_cle", name="uq_categorie_organisation_nom"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organisation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organisations.id"), index=True, nullable=False)
    nom: Mapped[str] = mapped_column(String(60), nullable=False)
    nom_cle: Mapped[str] = mapped_column(String(60), nullable=False)
    icone: Mapped[str] = mapped_column(String(40), nullable=False, default="autre")
    traductions: Mapped[str | None] = mapped_column(Text, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    date_creation: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_maintenant, nullable=False)
