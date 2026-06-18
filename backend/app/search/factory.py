from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.search.backfill import EmbeddingBackfillService, SQLEmbeddingBackfillRepository
from app.search.embedding import EmbeddingClient, OllamaEmbeddingClient
from app.search.indexer import SearchIndexService, SQLSearchIndexRepository
from app.search.semantic import SemanticSearchService, SQLFileEmbeddingRepository


def build_embedding_client(settings: Settings) -> EmbeddingClient | None:
    """An embedding client when semantic search is enabled, else None."""
    if not settings.embedding_enabled:
        return None
    base_url = settings.embedding_base_url or settings.llm_base_url
    return OllamaEmbeddingClient(
        base_url=base_url,
        model=settings.embedding_model,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.llm_api_key,
    )


def build_search_index_service(session: AsyncSession, settings: Settings) -> SearchIndexService:
    """Full-text indexer, with semantic embedding wired in when enabled."""
    client = build_embedding_client(settings)
    return SearchIndexService(
        SQLSearchIndexRepository(session),
        embedding_client=client,
        embedding_repo=SQLFileEmbeddingRepository(session) if client else None,
        embedding_model=settings.embedding_model,
    )


def build_semantic_search_service(
    session: AsyncSession, settings: Settings
) -> SemanticSearchService | None:
    """Semantic search service, or None when embeddings are disabled."""
    client = build_embedding_client(settings)
    if client is None:
        return None
    return SemanticSearchService(embedding_client=client, repo=SQLFileEmbeddingRepository(session))


def build_embedding_backfill_service(
    session: AsyncSession, settings: Settings
) -> EmbeddingBackfillService | None:
    """Service to backfill embeddings for already-indexed files, or None when
    embeddings are disabled."""
    client = build_embedding_client(settings)
    if client is None:
        return None
    return EmbeddingBackfillService(
        embedding_client=client,
        backfill_repo=SQLEmbeddingBackfillRepository(session),
        embedding_repo=SQLFileEmbeddingRepository(session),
        model=settings.embedding_model,
    )
