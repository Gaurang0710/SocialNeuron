"""Demo calendar generation and export helpers."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def generate_demo_calendar(days: int = 30) -> pd.DataFrame:
    today = date.today()
    platforms = ["LinkedIn", "X", "Instagram", "Facebook"]
    post_types = ["Educational", "Story", "Carousel", "Poll"]
    topics = [
        "Brand positioning tips",
        "Founder story",
        "Audience pain points",
        "Industry trend analysis",
        "Customer success insight",
        "Behind the scenes",
    ]
    rows = []
    for offset in range(1, days + 1):
        rows.append(
            {
                "Date": today + timedelta(days=offset),
                "Platform": platforms[(offset - 1) % len(platforms)],
                "Post Type": post_types[(offset - 1) % len(post_types)],
                "Topic": topics[(offset - 1) % len(topics)],
            }
        )
    return pd.DataFrame(rows)


def export_demo_calendar_excel(output_path: str | Path = "media/demo_files/demo_calendar.xlsx", days: int = 30) -> str:
    df = generate_demo_calendar(days=days)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    return str(path)

