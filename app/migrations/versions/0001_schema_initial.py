"""Schéma initial (étapes 1 à 9 bis)

Point de départ d'Alembic. Jusqu'à l'étape 9 bis, les tables étaient créées par
`Base.metadata.create_all` au démarrage de l'application. Cette migration ne
fait donc RIEN : elle sert de repère pour dire « la base est dans l'état de
l'étape 9 bis ». Les bases existantes (comme celle de développement) sont ainsi
prises en charge sans rien perdre.

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
