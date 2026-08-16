"""Filieres/sections on establishments, plus the indexes the read API needs.

Revision ID: 0002
Create Date: 2026-08-15

Why this exists:

- Ticket API-2 requires a `filiere` search filter and the fact-sheet identity
  block lists `filieres` and `sections`. The directory publishes both as
  `voie_*` and `section_*` flags; Phase 1's `DIRECTORY_FIELDS` simply did not
  read them. Stored as text[] rather than a join table: they are short, closed,
  descriptive tag lists with no attributes of their own.
- `ix_site_coordinates` supports the bounding-box pre-filter of the proximity
  search. The exact distance cut is a PostGIS call that cannot use a plain
  b-tree, so the box narrows the candidate set first.

Note there is deliberately no index on any indicator value: nothing in this
product orders establishments by a result, so an index that would make such an
ordering cheap has no legitimate caller.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "establishment",
        sa.Column(
            "filieres",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column(
        "establishment",
        sa.Column(
            "sections",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    # GIN: the filter is a containment test (`filieres @> ARRAY['generale']`).
    op.create_index(
        "ix_establishment_filieres",
        "establishment",
        ["filieres"],
        postgresql_using="gin",
    )
    op.create_index("ix_site_coordinates", "site", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("ix_site_coordinates", table_name="site")
    op.drop_index("ix_establishment_filieres", table_name="establishment")
    op.drop_column("establishment", "sections")
    op.drop_column("establishment", "filieres")
