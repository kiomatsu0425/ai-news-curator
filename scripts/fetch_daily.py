import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_curator.pipeline import run_daily


if __name__ == "__main__":
    stats = run_daily()
    print(stats)
