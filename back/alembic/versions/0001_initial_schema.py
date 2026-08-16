"""Initial schema — establishments, sites, indicator results, source references.

Revision ID: 0001
Create Date: 2026-08-15

Design notes, all traceable to docs/05_Resultats_Spike_Technique.md:

- `establishment.uai` is the primary key. The directory publishes one row per
  physical site and 74 UAIs have several, so sites live in their own table
  rather than duplicating the establishment. Nothing is dropped.
- `indicator_result` is append-only, keyed by (uai, year, indicator_type),
  which the spike verified strictly unique across 87 612 rows. There is no
  foreign key to `establishment`: ~1.2% of published indicator rows reference
  a UAI the directory does not (yet) contain, and refusing those rows would
  discard official data because of a gap in a different dataset.
- There is deliberately no `below_publication_threshold` column. The sources
  publish no reason for a missing value, and the documented candidate
  threshold does not predict the nulls.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "establishment",
        sa.Column("uai", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("department_code", sa.Text(), nullable=True),
        sa.Column(
            "is_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "site_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("source_updated_at", sa.Text(), nullable=True),
    )
    op.create_index("ix_establishment_type", "establishment", ["type"])
    op.create_index("ix_establishment_department", "establishment", ["department_code"])

    op.create_table(
        "site",
        sa.Column("uai", sa.Text(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("city_code", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("uai", "sequence"),
    )
    op.create_index("ix_site_city_code", "site", ["city_code"])
    op.create_index("ix_site_postal_code", "site", ["postal_code"])

    op.create_table(
        "indicator_result",
        sa.Column("uai", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("indicator_type", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("candidates_present", sa.Integer(), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=True),
        sa.Column("value_added_success", sa.Float(), nullable=True),
        sa.Column("access_rate", sa.Float(), nullable=True),
        sa.Column("value_added_access", sa.Float(), nullable=True),
        sa.Column("mention_rate", sa.Float(), nullable=True),
        sa.Column("value_added_mention", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("uai", "year", "indicator_type"),
    )
    op.create_index("ix_indicator_result_uai", "indicator_result", ["uai"])

    op.create_table(
        "source_reference",
        sa.Column("dataset_id", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("last_synchronised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_published_at", sa.Date(), nullable=True),
    )

    # One row per ingestion attempt — success or failure. DATA-5 needs this to
    # make a failed or suspicious run visible after the fact, not only in logs.
    op.create_table(
        "ingestion_run",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "succeeded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("establishments_loaded", sa.Integer(), nullable=True),
        sa.Column("indicators_loaded", sa.Integer(), nullable=True),
        sa.Column("indicators_seen", sa.Integer(), nullable=True),
        sa.Column("match_rate", sa.Float(), nullable=True),
        sa.Column("unmatched_uai_count", sa.Integer(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_ingestion_run_started_at", "ingestion_run", ["started_at"])


def downgrade() -> None:
    op.drop_table("ingestion_run")
    op.drop_table("source_reference")
    op.drop_table("indicator_result")
    op.drop_table("site")
    op.drop_table("establishment")
