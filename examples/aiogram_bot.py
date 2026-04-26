"""Минимальный aiogram-бот, отправляющий документ на подпись.

Запуск::

    pip install podpislon-sdk aiogram
    export TELEGRAM_BOT_TOKEN=...
    export PODPISLON_API_KEY=...
    python examples/aiogram_bot.py

Бот ждёт PDF и телефон в формате ``+7XXXXXXXXXX`` (в одном сообщении-ответе),
после чего отправляет ссылку на подписание.
"""

from __future__ import annotations

import asyncio
import io
import os
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from podpislon import PodpislonAPIError, PodpislonClient

router = Router()
PHONE_RE = re.compile(r"^\+7\d{10}$")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(
        "Привет! Пришлите PDF-документ, а в подписи к файлу укажите имя, "
        "фамилию и телефон через запятую: «Иван, Иванов, +79991112233»."
    )


@router.message(F.document)
async def on_document(message: Message, bot: Bot, podpislon: PodpislonClient) -> None:
    caption = (message.caption or "").strip()
    parts = [p.strip() for p in caption.split(",")]
    if len(parts) != 3 or not PHONE_RE.match(parts[2]):
        await message.answer(
            "Не понял подпись к файлу. Пример: «Иван, Иванов, +79991112233»"
        )
        return
    first_name, last_name, phone = parts

    file = await bot.get_file(message.document.file_id)
    buffer = io.BytesIO()
    await bot.download_file(file.file_path, destination=buffer)
    pdf_bytes = buffer.getvalue()

    try:
        result = await podpislon.documents.add(
            name=first_name,
            last_name=last_name,
            phone=phone,
            files=[pdf_bytes],
            file_names=[message.document.file_name or "document.pdf"],
            no_sms=True,
        )
    except PodpislonAPIError as exc:
        await message.answer(f"Подпислон вернул ошибку: {exc}")
        return

    if result.links:
        await message.answer(
            f"Готово! Ссылка на подписание:\n{result.first_link}"
        )
    else:
        await message.answer(
            f"Готово! Создан документ id={result.first_id}."
        )


async def main() -> None:
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    podpislon = PodpislonClient(api_key=os.environ["PODPISLON_API_KEY"])
    dp = Dispatcher()
    dp.include_router(router)

    try:
        # Передаём клиент SDK в роутеры через DI aiogram.
        await dp.start_polling(bot, podpislon=podpislon)
    finally:
        await podpislon.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
