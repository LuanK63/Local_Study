"""
utils/subject_loader.py
Discover and load all subject configs from subjects/ directory.
Adding a new subject = create subjects/<id>/config.yaml + topics.json.
"""
import yaml
import json
from pathlib import Path
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Optional

SUBJECTS_DIR = Path(__file__).parent.parent / "subjects"

@dataclass
class SubjectConfig:
    subject_id: str
    name: str
    name_en: str
    icon: str
    has_visualizer: bool
    code_language: str          # 'c_cpp' | 'python'
    chroma_collection: str
    languages: list[str]
    prompt_hints: dict
    topics: list[dict] = field(default_factory=list)
    documents_dir: Path = None

    @property
    def display_name(self) -> str:
        return f"{self.icon} {self.name}".strip() if self.icon else self.name


def _load_one(subject_dir: Path) -> Optional[SubjectConfig]:
    config_path = subject_dir / "config.yaml"
    topics_path = subject_dir / "topics.json"

    if not config_path.exists():
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    topics = []
    if topics_path.exists():
        with open(topics_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Flatten phases -> topics list
            for phase in data.get("phases", []):
                for t in phase.get("topics", []):
                    t["phase"] = phase["phase"]
                    t["phase_name"] = phase["name"]
                    topics.append(t)

    return SubjectConfig(
        subject_id      = cfg["subject_id"],
        name            = cfg["name"],
        name_en         = cfg.get("name_en", cfg["name"]),
        icon            = cfg.get("icon", ""),
        has_visualizer  = cfg.get("has_visualizer", False),
        code_language   = cfg.get("code_language", "python"),
        chroma_collection = cfg.get("chroma_collection", cfg["subject_id"]),
        languages       = cfg.get("languages", ["en"]),
        prompt_hints    = cfg.get("prompt_hints", {}),
        topics          = topics,
        documents_dir   = subject_dir / "documents",
    )


@lru_cache(maxsize=1)
def get_all_subjects() -> dict[str, SubjectConfig]:
    """Return dict[subject_id -> SubjectConfig] for all discovered subjects."""
    subjects = {}
    if not SUBJECTS_DIR.exists():
        return subjects
    for d in sorted(SUBJECTS_DIR.iterdir()):
        if d.is_dir():
            cfg = _load_one(d)
            if cfg:
                subjects[cfg.subject_id] = cfg
    return subjects


def get_subject(subject_id: str) -> SubjectConfig:
    subjects = get_all_subjects()
    if subject_id not in subjects:
        raise ValueError(f"Subject '{subject_id}' not found. Available: {list(subjects.keys())}")
    return subjects[subject_id]


def get_topic(subject_id: str, topic_id: str) -> Optional[dict]:
    cfg = get_subject(subject_id)
    for t in cfg.topics:
        if t["id"] == topic_id:
            return t
    return None
