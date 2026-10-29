"""Désarchivage et renommage de catégories (étape 18)

1. Ajoute la colonne « retention_depuis » à « objets » : date de départ du délai de conservation d'un objet
   désarchivé (vide pour tous les autres).
2. Renomme deux catégories dans les données existantes, pour que les anciens objets et déclarations
   continuent de se rapprocher des nouveaux :
   « Écouteurs » -> « Écouteurs ou baladeur » ; « Kit de maintenance et robotique » -> « Kit de maintenance ou de robotique ».

Idempotente, comme les migrations précédentes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

RENOMMAGES = {
    "Écouteurs": "Écouteurs ou baladeur",
    "Kit de maintenance et robotique": "Kit de maintenance ou de robotique",
}


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    tables = set(inspecteur.get_table_names())
    if "objets" in tables and "retention_depuis" not in {c["name"] for c in inspecteur.get_columns("objets")}:
        op.add_column("objets", sa.Column("retention_depuis", sa.DateTime(timezone=True), nullable=True))
    for table in ("objets", "signalements_perte"):
        if table not in tables:
            continue
        for ancien, nouveau in RENOMMAGES.items():
            op.execute(sa.text(f"UPDATE {table} SET categorie = :nouveau WHERE categorie = :ancien").bindparams(nouveau=nouveau, ancien=ancien))


def downgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if "objets" in inspecteur.get_table_names() and "retention_depuis" in {c["name"] for c in inspecteur.get_columns("objets")}:
        op.drop_column("objets", "retention_depuis")
