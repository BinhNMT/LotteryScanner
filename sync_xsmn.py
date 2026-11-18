"""CLI entrypoint to sync XSMN results from https://xsmn.mobi/ into SQLite."""

from __future__ import annotations

import sys

from lotto_store.scraper import main

if __name__ == "__main__":
    sys.exit(main())
