"""End-to-end example: send a document and poll until it's signed.

Run with:

    PODPISLON_API_KEY=your_key python examples/basic_usage.py path/to/contract.pdf

Note: this script is meant to be read; uncomment the polling loop only when
you have a real test document and a real signer phone number.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from podpislon import (
    DocumentStatus,
    Filter,
    PodpislonClient,
    PodpislonError,
)


async def main(pdf_path: Path) -> None:
    api_key = os.environ.get("PODPISLON_API_KEY")
    if not api_key:
        raise SystemExit("Set PODPISLON_API_KEY in the environment first.")

    async with PodpislonClient(api_key=api_key) as client:
        # 1. Account snapshot
        info = await client.company.get_info()
        print(f"Компания : {info.company.name}")
        print(f"ИНН      : {info.company.inn}")
        print(f"Остаток  : {info.signings_left} подписаний\n")

        # 2. Send a document
        result = await client.documents.add(
            name="Иван",
            last_name="Иванов",
            phone="+79991112233",  # ← подставьте реальный телефон подписанта
            files=[pdf_path],
            no_sms=True,           # вернёт ссылку вместо отправки SMS
        )
        print("Создан документ id =", result.first_id)
        if result.first_link:
            print("Ссылка для подписания:", result.first_link)

        # 3. List recent SIGNED documents
        page = await client.documents.list(
            page=1,
            filter=Filter(status=DocumentStatus.SIGNED),
        )
        print(f"\nПодписано документов на странице 1: {len(page)}")
        for doc in page.items[:5]:
            print(f"  {doc.id:>6} | {doc.status_text:<10} | {doc.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python examples/basic_usage.py path/to/contract.pdf")
        raise SystemExit(2)

    pdf = Path(sys.argv[1]).expanduser().resolve()
    if not pdf.is_file():
        raise SystemExit(f"File not found: {pdf}")

    try:
        asyncio.run(main(pdf))
    except PodpislonError as exc:
        print(f"Podpislon error: {exc}")
        raise SystemExit(1) from exc
