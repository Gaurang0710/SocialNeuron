"""Demo calendar generation and export helpers."""
from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def generate_demo_calendar(days: int = 5) -> pd.DataFrame:
    today = date.today()

    platform_content_map = {
        "LinkedIn": [
            "Text Post",
            "Carousel",
        ],
        "Instagram": [
            "Carousel",
            "Reel",
        ],
        "Facebook": [
            "Text Post",
        ],
        "X": [
            "Thread",

        ],
        "YouTube": [
            "Long-form Video",
            "Short",
        ]
    }

    topics = [
        "Brand positioning tips",
        "Founder story",
        "Audience pain points",
        "Industry trend analysis",
        "Customer success insight",
        "Behind the scenes",
        "Product feature highlight",
        "Case study",
        "Expert opinion",
        "FAQ",
    ]

    platforms = list(platform_content_map.keys())

    rows = []
    for offset in range(days):
        platform = platforms[offset % len(platforms)]

        rows.append(
            {
                "Date": today + timedelta(days=offset),
                "Platform": platform,
                "Content Type": random.choice(
                    platform_content_map[platform]
                ),
                "Topic": topics[offset % len(topics)],
            }
        )

    return pd.DataFrame(rows)


def export_demo_calendar_excel(output_path: str | Path = "media/demo_files/demo_calendar.xlsx", days: int = 5) -> str:
    df = generate_demo_calendar(days=days)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    return str(path)

