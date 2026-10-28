"""Matricule de l'étudiant à la restitution (étape 16 bis)

Ajoute la colonne facultative « matricule_etudiant » à la table « restitutions ». Les restitutions existantes
gardent une valeur vide. Idempotente, comme les migrations précédentes.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLE = "restitutions"
COLONNE = "matricule_etudiant"


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if TABLE not in inspecteur.get_table_names():
        return  # base vide : create_all créera la table avec sa colonne
    if COLONNE not in {c["name"] for c in inspecteur.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLONNE, sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column(TABLE, COLONNE)
