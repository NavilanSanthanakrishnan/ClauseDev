from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[5] / ".env.clauseainaviprod"),
        env_prefix="CLAUSE_",
        case_sensitive=False,
    )

    app_name: str = "Clause API"
    debug: bool = True
    database_path: Path = Path(__file__).resolve().parents[4] / "database" / "clause.sqlite3"
    schema_path: Path = Path(__file__).resolve().parents[4] / "database" / "schema.sql"
    seed_path: Path = Path(__file__).resolve().parents[4] / "database" / "seed" / "bills.json"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_timeout_seconds: float = 20.0
    default_limit: int = 12
    max_candidate_pool: int = 60
    semantic_weight: float = 0.35
    lexical_weight: float = 0.65
    topic_expansions: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "privacy": ["data", "consumer", "broker", "deletion", "surveillance"],
            "healthcare": ["medicaid", "hospital", "payment", "reimbursement", "coverage"],
            "energy": ["grid", "utility", "emissions", "reliability", "climate"],
            "housing": ["tenant", "landlord", "rent", "eviction", "affordability"],
        }
    )


settings = Settings()
