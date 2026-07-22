import csv
import json
from pathlib import Path
from models.keyword import KeywordDiscoveryResult


def write_json(result: KeywordDiscoveryResult, output_path: str) -> None:
    """Writes KeywordDiscoveryResult to JSON file matching Section 1 schema."""
    data = result.model_dump()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_csv(result: KeywordDiscoveryResult, output_path: str) -> None:
    """Exports KeywordDiscoveryResult to a flat CSV file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "term",
        "type",
        "word_count",
        "intent",
        "source",
        "volume",
        "difficulty",
        "relevance_score",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for kw in result.keywords:
            writer.writerow(
                [
                    kw.term,
                    kw.type,
                    kw.word_count,
                    kw.intent,
                    ",".join(kw.source),
                    kw.volume if kw.volume is not None else "",
                    kw.difficulty if kw.difficulty is not None else "",
                    kw.relevance_score,
                ]
            )
