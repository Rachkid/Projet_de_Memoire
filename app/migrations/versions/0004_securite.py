"""Sécurité des comptes (étape 16)

Ajoute à « utilisateurs » :
  - version_session : numéro de génération des sessions (invalide les jetons après changement de mot de passe) ;
  - doit_changer_mot_de_passe : vrai tant que le mot de passe est provisoire.
La table « journal_audit » est créée au démarrage par create_all (nouvelle table).

Comme les migrations précédentes, elle est « idempotente » : elle n'ajoute que les colonnes manquantes.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLE = "utilisateurs"


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if TABLE not in inspecteur.get_table_names():
        return  # base vide : create_all créera la table avec ses colonnes
    existantes = {c["name"] for c in inspecteur.get_columns(TABLE)}
    if "version_session" not in existantes:
        op.add_column(TABLE, sa.Column("version_session", sa.Integer(), nullable=False, server_default="0"))
    if "doit_changer_mot_de_passe" not in existantes:
        op.add_column(TABLE, sa.Column("doit_changer_mot_de_passe", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column(TABLE, "doit_changer_mot_de_passe")
    op.drop_column(TABLE, "version_session")
