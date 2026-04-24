"""Runtime configuration read from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings block. All values come from the `.env` file at the repo root."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tinyfish_api_key: str = Field(default="", validation_alias="TINYFISH_API_KEY")

    redis_url: str = Field(
        default="redis://localhost:6379", validation_alias="REDIS_URL"
    )

    frontend_origin: str = Field(
        default="http://localhost:5173", validation_alias="FRONTEND_ORIGIN"
    )
    cosmo_router_url: str = Field(
        default="http://localhost:3002", validation_alias="COSMO_ROUTER_URL"
    )

    mock_tinyfish: bool = Field(default=False, validation_alias="MOCK_TINYFISH")
    academic_mode: bool = Field(default=False, validation_alias="ACADEMIC_MODE")
    citation_traversal_depth: int = Field(
        default=1, validation_alias="CITATION_TRAVERSAL_DEPTH"
    )
    citation_branch_limit: int = Field(
        default=5, validation_alias="CITATION_BRANCH_LIMIT"
    )
    allowed_academic_domains: str = Field(
        default="arxiv.org,semanticscholar.org,pubmed.ncbi.nlm.nih.gov,scholar.google.com",
        validation_alias="ALLOWED_ACADEMIC_DOMAINS",
    )
    redis_native_pipeline: bool = Field(
        default=True, validation_alias="REDIS_NATIVE_PIPELINE"
    )
    redis_raw_stream: str = Field(
        default="nexus:stream:raw_extract", validation_alias="REDIS_RAW_STREAM"
    )
    redis_dlq_stream: str = Field(
        default="nexus:stream:dlq", validation_alias="REDIS_DLQ_STREAM"
    )
    redis_stream_group: str = Field(
        default="normalizer-group", validation_alias="REDIS_STREAM_GROUP"
    )
    redis_stream_consumer: str = Field(
        default="normalizer-1", validation_alias="REDIS_STREAM_CONSUMER"
    )
    redis_stream_batch_size: int = Field(
        default=50, validation_alias="REDIS_STREAM_BATCH_SIZE"
    )
    redis_stream_block_ms: int = Field(
        default=3000, validation_alias="REDIS_STREAM_BLOCK_MS"
    )
    redis_context_top_k: int = Field(
        default=5, validation_alias="REDIS_CONTEXT_TOP_K"
    )
    redis_context_cache_ttl_seconds: int = Field(
        default=600, validation_alias="REDIS_CONTEXT_CACHE_TTL_SECONDS"
    )
    redis_embedding_cache_ttl_seconds: int = Field(
        default=86400, validation_alias="REDIS_EMBEDDING_CACHE_TTL_SECONDS"
    )
    redis_vector_enabled: bool = Field(
        default=True, validation_alias="REDIS_VECTOR_ENABLED"
    )
    redis_vector_index_name: str = Field(
        default="nexus:idx:context", validation_alias="REDIS_VECTOR_INDEX_NAME"
    )
    embedding_api_base: str = Field(
        default="https://api.openai.com/v1", validation_alias="EMBEDDING_API_BASE"
    )
    embedding_api_key: str = Field(default="", validation_alias="EMBEDDING_API_KEY")
    embedding_model: str = Field(
        default="text-embedding-3-small", validation_alias="EMBEDDING_MODEL"
    )
    embedding_dimension: int = Field(default=1536, validation_alias="EMBEDDING_DIMENSION")
    min_evidence_sources: int = Field(default=3, validation_alias="MIN_EVIDENCE_SOURCES")
    min_evidence_findings: int = Field(default=4, validation_alias="MIN_EVIDENCE_FINDINGS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor so FastAPI Depends() doesn't re-read env repeatedly."""
    return Settings()
