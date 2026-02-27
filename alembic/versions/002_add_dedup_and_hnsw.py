"""Add dedup fingerprint columns and HNSW vector index.

Revision ID: 002_dedup_hnsw
Revises: 001_initial
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa

revision = "002_dedup_hnsw"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "articles",
        sa.Column("title_simhash", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "articles",
        sa.Column(
            "content_minhash",
            sa.ARRAY(sa.BigInteger()),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_articles_title_simhash",
        "articles",
        ["title_simhash"],
    )
    # HNSW index for cosine similarity on embedding column
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_articles_embedding_hnsw
        ON articles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_articles_embedding_hnsw")
    op.drop_index("idx_articles_title_simhash", table_name="articles")
    op.drop_column("articles", "content_minhash")
    op.drop_column("articles", "title_simhash")
