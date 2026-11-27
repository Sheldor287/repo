"""Allow running the scraper with ``python -m cfb_scraper``."""
from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
