"""
Tests for storage/models.py -- Source, Article, and FetchLog ORM models.

These tests verify default values, column configurations, and UUID
generation logic without hitting a real database.
"""

import uuid

import pytest

from storage.models import Article, FetchLog, Source


class TestSourceModelDefaults:
    """Verify default column values on the Source model."""

    def test_default_enabled_is_true(self):
        """The enabled column should default to True."""
        col = Source.__table__.columns["enabled"]
        assert col.default.arg is True

    def test_default_priority_is_5(self):
        """The priority column should default to 5."""
        col = Source.__table__.columns["priority"]
        assert col.default.arg == 5

    def test_default_fetch_interval_is_30(self):
        """fetch_interval_minutes should default to 30."""
        col = Source.__table__.columns["fetch_interval_minutes"]
        assert col.default.arg == 30

    def test_default_health_status_is_healthy(self):
        """health_status should default to 'healthy'."""
        col = Source.__table__.columns["health_status"]
        assert col.default.arg == "healthy"

    def test_source_id_is_primary_key(self):
        """source_id should be the primary key."""
        col = Source.__table__.columns["source_id"]
        assert col.primary_key

    def test_name_not_nullable(self):
        """name column should not be nullable."""
        col = Source.__table__.columns["name"]
        assert col.nullable is False

    def test_url_not_nullable(self):
        """url column should not be nullable."""
        col = Source.__table__.columns["url"]
        assert col.nullable is False

    def test_created_at_has_server_default(self):
        """created_at should have a server_default (func.now())."""
        col = Source.__table__.columns["created_at"]
        assert col.server_default is not None


class TestArticleModelDefaults:
    """Verify default column values on the Article model."""

    def test_default_processing_status(self):
        """processing_status should default to 'pending'."""
        col = Article.__table__.columns["processing_status"]
        assert col.default.arg == "pending"

    def test_default_llm_processed(self):
        """llm_processed should default to False."""
        col = Article.__table__.columns["llm_processed"]
        assert col.default.arg is False

    def test_url_is_unique(self):
        """url column should have a unique constraint."""
        col = Article.__table__.columns["url"]
        assert col.unique is True

    def test_url_not_nullable(self):
        """url column should not be nullable."""
        col = Article.__table__.columns["url"]
        assert col.nullable is False

    def test_title_not_nullable(self):
        """title column should not be nullable."""
        col = Article.__table__.columns["title"]
        assert col.nullable is False

    def test_source_id_indexed(self):
        """source_id should be indexed for fast lookups."""
        col = Article.__table__.columns["source_id"]
        assert col.index is True

    def test_fetched_at_has_server_default(self):
        """fetched_at should have a server_default."""
        col = Article.__table__.columns["fetched_at"]
        assert col.server_default is not None

    def test_id_is_primary_key(self):
        """id should be the primary key."""
        col = Article.__table__.columns["id"]
        assert col.primary_key


class TestFetchLogModelDefaults:
    """Verify default column values on the FetchLog model."""

    def test_default_articles_found_is_zero(self):
        """articles_found should default to 0."""
        col = FetchLog.__table__.columns["articles_found"]
        assert col.default.arg == 0

    def test_default_articles_new_is_zero(self):
        """articles_new should default to 0."""
        col = FetchLog.__table__.columns["articles_new"]
        assert col.default.arg == 0

    def test_default_articles_dedup_is_zero(self):
        """articles_dedup should default to 0."""
        col = FetchLog.__table__.columns["articles_dedup"]
        assert col.default.arg == 0

    def test_id_is_primary_key(self):
        """id should be the primary key."""
        col = FetchLog.__table__.columns["id"]
        assert col.primary_key

    def test_id_autoincrement(self):
        """id should be auto-incremented."""
        col = FetchLog.__table__.columns["id"]
        assert col.autoincrement is True or col.autoincrement == "auto"

    def test_source_id_not_nullable(self):
        """source_id should not be nullable."""
        col = FetchLog.__table__.columns["source_id"]
        assert col.nullable is False

    def test_source_id_indexed(self):
        """source_id should be indexed."""
        col = FetchLog.__table__.columns["source_id"]
        assert col.index is True


class TestArticleUuidGeneration:
    """The Article.id default should produce valid UUID4 strings."""

    def test_default_generates_uuid_string(self):
        """The id default callable should return a valid UUID4 string."""
        col = Article.__table__.columns["id"]
        generated = col.default.arg()
        # Should be a valid UUID string
        parsed = uuid.UUID(generated)
        assert parsed.version == 4

    def test_default_generates_unique_values(self):
        """Each call to the default should produce a unique UUID."""
        col = Article.__table__.columns["id"]
        ids = {col.default.arg() for _ in range(100)}
        assert len(ids) == 100

    def test_uuid_format(self):
        """Generated UUID should be the standard 36-char hyphenated format."""
        col = Article.__table__.columns["id"]
        generated = col.default.arg()
        assert len(generated) == 36
        assert generated.count("-") == 4
