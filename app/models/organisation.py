"""
Modèle Organisation : représente un établissement scolaire/universitaire ou
une compagnie de transport cliente du système. C'est le pivot de
l'architecture multi-tenant décrite au chapitre 3 du mémoire (section 3.1) :
toutes les autres tables lui sont rattachées, directement ou indirectement,
afin de garantir une isolation stricte des données entre organisations.
"""

import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)

    # "education" ou "transport" (voir app/models/enums.py : SecteurOrganisation)
    secteur: Mapped[str] = mapped_column(String(20), nullable=False)

    # Options propres à chaque organisation (cahier des charges, section 5.1.2 et 5.1.5)
    consultation_distance: Mapped[bool] = mapped_column(Boolean, default=False)
    delai_retention_jours: Mapped[int] = mapped_column(Integer, default=90)

    # Habillage (Étape 10) : ce qui fait reconnaître l'organisation au premier regard.
    # Tout est facultatif : sans choix, l'interface utilise le thème par défaut de Retrova.
    # - slug : identifiant court utilisé dans l'adresse des pages (ex. : « iat » -> /iat)
    # - logo_url / fond_url : adresses publiques des images enregistrées sur le serveur
    # - couleurs au format #rrggbb
    slug: Mapped[str | None] = mapped_column(String(50), unique=True, index=True, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fond_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    couleur_principale: Mapped[str | None] = mapped_column(String(7), nullable=True)
    couleur_accent: Mapped[str | None] = mapped_column(String(7), nullable=True)
    couleur_fond: Mapped[str | None] = mapped_column(String(7), nullable=True)

    # Relations vers les tables qui appartiennent à cette organisation.
    # back_populates crée le lien dans les deux sens : depuis une Organisation,
    # on peut lister ses utilisateurs (organisation.utilisateurs), et depuis un
    # Utilisateur, on peut retrouver son organisation (utilisateur.organisation).
    utilisateurs: Mapped[list["Utilisateur"]] = relationship(back_populates="organisation")
    objets: Mapped[list["Objet"]] = relationship(back_populates="organisation")
    signalements: Mapped[list["SignalementPerte"]] = relationship(back_populates="organisation")

    def __repr__(self) -> str:
        return f"<Organisation {self.nom} ({self.secteur})>"
