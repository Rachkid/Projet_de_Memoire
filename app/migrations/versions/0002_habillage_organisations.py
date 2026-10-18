"""Habillage des organisations (étape 10)

Ajoute à la table « organisations » : l'identifiant court d'adresse (slug), le
logo, la photo de fond et les trois couleurs.

La migration est « idempotente » : elle ajoute une colonne seulement si elle
n'existe pas déjà. C'est nécessaire parce que, sur une base TOUTE NEUVE, la création
des tables au démarrage (create_all) les crée déjà avec ces colonnes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLE = "organisations"
COLONNES = [
    ("slug", sa.String(50)),
    ("logo_url", sa.String(255)),
    ("fond_url", sa.String(255)),
    ("couleur_principale", sa.String(7)),
    ("couleur_accent", sa.String(7)),
    ("couleur_fond", sa.String(7)),
]
INDEX_SLUG = "ix_organisations_slug"


def upgrade() -> None:
    inspecteur = sa.inspect(op.get_bind())
    if TABLE not in inspecteur.get_table_names():
        return  # base vide : create_all créera la table avec toutes ses colonnes
    existantes = {c["name"] for c in inspecteur.get_columns(TABLE)}
    for nom, type_ in COLONNES:
        if nom not in existantes:
            op.add_column(TABLE, sa.Column(nom, type_, nullable=True))
    if INDEX_SLUG not in {i["name"] for i in inspecteur.get_indexes(TABLE)}:
        # Index UNIQUE : deux organisations ne peuvent pas avoir le même slug.
        # (PostgreSQL accepte plusieurs valeurs NULL : les organisations sans slug ne se gênent pas.)
        op.create_index(INDEX_SLUG, TABLE, ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX_SLUG, table_name=TABLE)
    for nom, _ in reversed(COLONNES):
        op.drop_column(TABLE, nom)
