"""Quick smoke test for the offline English/Hindi translation pipeline."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
for candidate in (str(PROJECT_ROOT), str(BACKEND_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from backend.services.offline_translator import translate_to_english

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEST_PHRASES = [
    ("en", "patient has severe chest pain and difficulty breathing"),
    ("hi", "seene mein bahut dard ho raha hai aur sans lene mein takleef hai"),
]


async def main() -> None:
    for lang_code, phrase in TEST_PHRASES:
        print(f"\nLanguage: {lang_code}")
        print(f"Original: {phrase}")
        result = await translate_to_english(phrase, lang_code)
        print(f"Translated: {result['translated_text']}")
        print(f"Model: {result['model_used']}")


if __name__ == "__main__":
    asyncio.run(main())
