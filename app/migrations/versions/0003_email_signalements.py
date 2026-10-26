"""E-mail facultatif sur les signalements de perte (étape 15)

Ajoute la colonne « email » à la table « signalements_perte ». Elle est facultative :
les signalements existants gardent simplement une valeur vide.

Comme la migration 0002, elle est « idempotente » : elle n'ajoute la colonne que si elle
n'existe pas déjà (sur une base toute neuve, create_all l'a déjà créée).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLE = "signalements_perte"
COLONNE = "email"


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if TABLE not in inspecteur.get_table_names():
        return  # base vide : create_all créera la table avec sa colonne
    if COLONNE not in {c["name"] for c in inspecteur.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(254), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, COLONNE)
