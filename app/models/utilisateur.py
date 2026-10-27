"""
Modèle Utilisateur : représente une personne disposant d'un compte dans le
système (agent, administrateur d'établissement, super-administrateur).
À ne pas confondre avec le modèle Usager, qui représente une personne
extérieure (élève, voyageur) sans compte ni mot de passe (voir usager.py).
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Utilisateur(Base):
    __tablename__ = "utilisateurs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organisations.id"), nullable=False
    )

    # Identifiant de connexion, unique dans tout le système (stocké en minuscules).
    identifiant: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    nom: Mapped[str] = mapped_column(String(150), nullable=False)

    # "agent", "administrateur" ou "super_administrateur"
    # (voir app/models/enums.py : RoleUtilisateur)
    role: Mapped[str] = mapped_column(String(30), nullable=False)

    # Les deux droits sont indépendants l'un de l'autre : un même agent peut
    # cumuler les deux, ou n'en avoir qu'un seul, selon la configuration
    # retenue par son organisation (mémoire, chapitre 2, section 2.2).
    droit_enregistrement: Mapped[bool] = mapped_column(Boolean, default=False)
    droit_restitution: Mapped[bool] = mapped_column(Boolean, default=False)

    # Un compte n'est jamais supprimé (les objets et restitutions qu'il a
    # traités doivent rester traçables) : il est simplement désactivé.
    actif: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Mot de passe chiffré avec bcrypt (jamais stocké en clair).
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # Étape 16 : numéro de « génération » des sessions. Chaque jeton de connexion porte le numéro courant ; on
    # l'augmente quand le mot de passe change, est réinitialisé ou que le compte est désactivé : tous les jetons
    # déjà émis (par exemple sur un téléphone volé) cessent aussitôt de fonctionner.
    version_session: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    # Étape 16 : vrai tant que le mot de passe est PROVISOIRE (compte créé ou réinitialisé par un administrateur).
    # Tant qu'il l'est, le serveur ne laisse faire que « voir mon profil » et « changer mon mot de passe ».
    doit_changer_mot_de_passe: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    organisation: Mapped["Organisation"] = relationship(back_populates="utilisateurs")
    objets_enregistres: Mapped[list["Objet"]] = relationship(back_populates="agent_enregistrement")
    restitutions_validees: Mapped[list["Restitution"]] = relationship(back_populates="agent_restitution")

    def __repr__(self) -> str:
        return f"<Utilisateur {self.nom} ({self.role})>"
