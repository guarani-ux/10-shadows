import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class ScribeMemoryStore:
    """
    Shadow 6 (The Scribe) Memory & Knowledge Engine.
    
    SQLite WAL-backed relational store for indexing, querying,
    and cross-referencing narrative blueprints, hook patterns,
    and epistemic anomalies across arbitrary videos.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (Path("scratch/scribe_memory.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    duration_formatted TEXT NOT NULL,
                    total_words INTEGER NOT NULL,
                    overall_wpm REAL NOT NULL,
                    core_subject TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS scenes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    scene_index INTEGER NOT NULL,
                    time_window TEXT NOT NULL,
                    start_seconds REAL NOT NULL,
                    end_seconds REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    words_count INTEGER NOT NULL,
                    pacing_wpm REAL NOT NULL,
                    summary TEXT NOT NULL,
                    verbatim_anchor_quote TEXT NOT NULL,
                    FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS blindspots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    time_window TEXT NOT NULL,
                    anomaly_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    gap_duration_seconds REAL,
                    FOREIGN KEY(video_id) REFERENCES videos(video_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_scenes_video_id ON scenes(video_id);
                CREATE INDEX IF NOT EXISTS idx_blindspots_video_id ON blindspots(video_id);
                """
            )

    def index_blueprint(self, blueprint_data: Dict[str, Any]) -> str:
        """Atomically inserts or updates a video blueprint and its relational scenes."""
        video_id = blueprint_data["video_id"]

        with self._get_connection() as conn:
            # 1. Upsert video header
            conn.execute(
                """
                INSERT INTO videos (video_id, title, channel, duration_formatted, total_words, overall_wpm, core_subject)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(video_id) DO UPDATE SET
                    title=excluded.title,
                    channel=excluded.channel,
                    duration_formatted=excluded.duration_formatted,
                    total_words=excluded.total_words,
                    overall_wpm=excluded.overall_wpm,
                    core_subject=excluded.core_subject;
                """,
                (
                    video_id,
                    blueprint_data["title"],
                    blueprint_data["channel"],
                    blueprint_data["duration_formatted"],
                    blueprint_data["total_words"],
                    blueprint_data["overall_wpm"],
                    blueprint_data["core_subject"],
                ),
            )

            # 2. Re-index scenes
            conn.execute("DELETE FROM scenes WHERE video_id = ?", (video_id,))
            for s in blueprint_data.get("scenes", []):
                conn.execute(
                    """
                    INSERT INTO scenes (
                        video_id, scene_index, time_window, start_seconds,
                        end_seconds, duration_seconds, words_count,
                        pacing_wpm, summary, verbatim_anchor_quote
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        video_id,
                        s["scene_index"],
                        s["time_window"],
                        s["start_seconds"],
                        s["end_seconds"],
                        s["duration_seconds"],
                        s["words_count"],
                        s["pacing_wpm"],
                        s["summary"],
                        s["verbatim_anchor_quote"],
                    ),
                )

            # 3. Re-index blindspots
            conn.execute("DELETE FROM blindspots WHERE video_id = ?", (video_id,))
            for b in blueprint_data.get("known_blindspots", []):
                conn.execute(
                    """
                    INSERT INTO blindspots (
                        video_id, time_window, anomaly_type,
                        description, gap_duration_seconds
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        video_id,
                        b["time_window"],
                        b["anomaly_type"],
                        b["description"],
                        b.get("gap_duration_seconds"),
                    ),
                )

        return video_id

    def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves fully populated video blueprint with scenes and blindspots."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
            if not row:
                return None

            video_dict = dict(row)
            scenes = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM scenes WHERE video_id = ? ORDER BY scene_index ASC", (video_id,)
                ).fetchall()
            ]
            blindspots = [
                dict(r) for r in conn.execute(
                    "SELECT * FROM blindspots WHERE video_id = ?", (video_id,)
                ).fetchall()
            ]

            video_dict["scenes"] = scenes
            video_dict["known_blindspots"] = blindspots
            return video_dict

    def query_by_channel(self, channel: str) -> List[Dict[str, Any]]:
        """Finds all indexed videos produced by a specific channel."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM videos WHERE channel = ?", (channel,)).fetchall()
            return [dict(r) for r in rows]

    def get_pacing_statistics(self) -> Dict[str, Any]:
        """Calculates global corpus telemetry across all indexed videos."""
        with self._get_connection() as conn:
            row = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_videos,
                    AVG(overall_wpm) as avg_wpm,
                    AVG(total_words) as avg_word_count
                FROM videos
                """
            ).fetchone()
            return {
                "total_indexed_videos": row["total_videos"] if row else 0,
                "corpus_avg_wpm": round(row["avg_wpm"] or 0.0, 1),
                "corpus_avg_word_count": round(row["avg_word_count"] or 0.0, 1),
            }
