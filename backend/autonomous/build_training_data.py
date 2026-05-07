"""
CLI entrypoint for building internet-sourced training data.
"""

from __future__ import annotations

import argparse
import json

from .internet_training_data import InternetTrainingDataBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="Build internet-sourced NEPSE training data.")
    parser.add_argument(
        "--profile",
        choices=["high_level", "advanced"],
        default="advanced",
        help="High-level builds market/macro/news quickly; advanced adds fundamentals and company-specific news.",
    )
    parser.add_argument("--symbol-limit", type=int, default=None, help="Optional limit for smoke tests or partial refreshes.")
    parser.add_argument("--refresh", action="store_true", help="Overwrite existing files instead of reusing them.")
    parser.add_argument("--market-news-pages", type=int, default=5, help="Number of ShareSansar latest-news pages to ingest.")
    parser.add_argument(
        "--market-article-body-limit",
        type=int,
        default=30,
        help="How many latest market articles should have full bodies downloaded instead of title-only rows.",
    )
    args = parser.parse_args()

    builder = InternetTrainingDataBuilder()
    summary = builder.build(
        profile=args.profile,
        symbol_limit=args.symbol_limit,
        refresh=args.refresh,
        market_news_pages=args.market_news_pages,
        market_article_body_limit=args.market_article_body_limit,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
