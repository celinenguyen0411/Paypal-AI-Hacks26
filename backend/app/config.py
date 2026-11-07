import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

TZ = ZoneInfo("America/Chicago")


@dataclass(frozen=True)
class Settings:
    database_path: str
    demo_mode: bool
    cors_origins: tuple[str, ...]
    places_path: Path
    groq_api_key: str = field(repr=False)
    groq_model: str
    groq_timeout_s: float
    demo_safe_to_spend_cents: int

    @classmethod
    def from_env(cls, db_path=None, demo_mode=None, places_path=None):
        # Read the backend's .env without modifying process-wide environment state.
        environment = {**dotenv_values(Path(__file__).resolve().parent.parent / ".env"), **os.environ}
        get = environment.get
        timeout = float(get("GROQ_TIMEOUT_S", "20"))
        balance = int(get("DEMO_SAFE_TO_SPEND_CENTS", "6400"))
        if not 0 < timeout <= 120 or balance < 0:
            raise ValueError("GROQ_TIMEOUT_S must be in (0, 120]; demo balance must be nonnegative.")
        return cls(
            database_path=str(db_path or get(
                "MAP_DB_PATH", Path(__file__).resolve().parent.parent / "map.sqlite3")),
            demo_mode=(get("MAP_DEMO_MODE", "true").lower() == "true"
                       if demo_mode is None else demo_mode),
            cors_origins=tuple(origin.strip() for origin in get(
                "MAP_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")),
            places_path=Path(places_path or get(
                "MAP_PLACES_PATH", Path(__file__).resolve().parent.parent / "data/raw/entities.json")),
            groq_api_key=get("GROQ_API_KEY", "") or "",
            groq_model=get("GROQ_MODEL", "openai/gpt-oss-20b"),
            groq_timeout_s=timeout,
            demo_safe_to_spend_cents=balance,
        )
