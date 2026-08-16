"""Official commune reference and deterministic identity-search indexes.

Revision ID: 0003
Create Date: 2026-08-15

Text search is deliberately limited to factual identity fields. Result values
are neither stored here nor indexed for cross-establishment ordering.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # PostgreSQL's unaccent() is stable rather than immutable, so generated
    # columns cannot call it directly. This wrapper is safe for our fixed
    # dictionary and gives writes and query parameters one normalization path.
    op.execute(
        """
        CREATE FUNCTION normalize_search_text(value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE PARALLEL SAFE STRICT
        AS $$
            SELECT btrim(regexp_replace(
                lower(public.unaccent('public.unaccent', value)),
                '[^[:alnum:]]+', ' ', 'g'
            ))
        $$
        """
    )

    op.add_column(
        "establishment",
        sa.Column(
            "search_name",
            sa.Text(),
            sa.Computed("normalize_search_text(name)", persisted=True),
        ),
    )
    op.add_column(
        "site",
        sa.Column(
            "search_city",
            sa.Text(),
            sa.Computed("normalize_search_text(city)", persisted=True),
        ),
    )
    op.create_index(
        "ix_establishment_search_name_trgm",
        "establishment",
        ["search_name"],
        postgresql_using="gin",
        postgresql_ops={"search_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_site_search_city_trgm",
        "site",
        ["search_city"],
        postgresql_using="gin",
        postgresql_ops={"search_city": "gin_trgm_ops"},
    )

    op.create_table(
        "commune",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "search_name",
            sa.Text(),
            sa.Computed("normalize_search_text(name)", persisted=True),
        ),
        sa.Column(
            "postal_codes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("department_code", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_commune_coordinates_paired",
        ),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name="ck_commune_latitude_range",
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name="ck_commune_longitude_range",
        ),
    )
    op.create_index(
        "ix_commune_search_name_trgm",
        "commune",
        ["search_name"],
        postgresql_using="gin",
        postgresql_ops={"search_name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_commune_postal_codes",
        "commune",
        ["postal_codes"],
        postgresql_using="gin",
    )

    op.add_column(
        "ingestion_run",
        sa.Column("communes_loaded", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_run", "communes_loaded")
    op.drop_table("commune")
    op.drop_index("ix_site_search_city_trgm", table_name="site")
    op.drop_index("ix_establishment_search_name_trgm", table_name="establishment")
    op.drop_column("site", "search_city")
    op.drop_column("establishment", "search_name")
    op.execute("DROP FUNCTION normalize_search_text(text)")
