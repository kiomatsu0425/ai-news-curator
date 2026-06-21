from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news_curator.postgres_store import reset_mojibake_summaries


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print(json.dumps(reset_mojibake_summaries(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
