import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")


@dataclass(frozen=True)
class Settings:
    database_path: str
    demo_mode: bool
    cors_origins: tuple[str, ...]
    places_path: Path

    @classmethod
    def from_env(cls, db_path=None, demo_mode=None, places_path=None):
        return cls(
            database_path=str(db_path or os.getenv(
                "MAP_DB_PATH", Path(__file__).resolve().parent.parent / "map.sqlite3")),
            demo_mode=(os.getenv("MAP_DEMO_MODE", "true").lower() == "true"
                       if demo_mode is None else demo_mode),
            cors_origins=tuple(origin.strip() for origin in os.getenv(
                "MAP_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")),
            places_path=Path(places_path or os.getenv(
                "MAP_PLACES_PATH", Path(__file__).resolve().parent.parent / "data/raw/entities.json")),
        )
