# podpislon-sdk

[![PyPI version](https://img.shields.io/pypi/v/podpislon-sdk.svg)](https://pypi.org/project/podpislon-sdk/)
[![Python versions](https://img.shields.io/pypi/pyversions/podpislon-sdk.svg)](https://pypi.org/project/podpislon-sdk/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/IceOne-i/podpislon-sdk/actions/workflows/tests.yml/badge.svg)](https://github.com/IceOne-i/podpislon-sdk/actions/workflows/tests.yml)
[![PyPI publish](https://github.com/IceOne-i/podpislon-sdk/actions/workflows/publish.yml/badge.svg)](https://github.com/IceOne-i/podpislon-sdk/actions/workflows/publish.yml)

> 🇷🇺 **Asynchronous Python SDK for the [Podpislon](https://podpislon.ru) document-signing API.**
> Built on `httpx` + `pydantic v2`. Ships first-class typing, rate limiting, retries, paginated iterators, and a webhook handler that drops straight into FastAPI / aiogram / aiohttp.

---

## ⚠️ Disclaimer

> **Этот проект — НЕОФИЦИАЛЬНЫЙ SDK.**
>
> Он создан и поддерживается сообществом. Этот SDK **не является официальным**, **не имеет отношения** к компании, владеющей сервисом [https://podpislon.ru](https://podpislon.ru), не одобрен и не спонсирован ею. Все упомянутые торговые марки и названия принадлежат их законным владельцам.
>
> Используете на свой страх и риск. Авторы и контрибьюторы не несут ответственности за любые последствия использования этой библиотеки.
>
> ---
>
> **This project is an UNOFFICIAL SDK.**
>
> It is community-maintained and is **NOT affiliated with**, endorsed by, sponsored by, or in any way officially connected with the company operating [https://podpislon.ru](https://podpislon.ru). All trademarks and product names mentioned belong to their respective owners.
>
> Use at your own risk. The authors and contributors are not liable for any consequences arising from the use of this library.

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Аутентификация](#аутентификация)
- [Работа с документами](#работа-с-документами)
  - [Список документов](#список-документов)
  - [Постраничный обход](#постраничный-обход)
  - [Фильтрация](#фильтрация)
  - [Отправка документа на подпись](#отправка-документа-на-подпись)
  - [Получение PDF](#получение-pdf)
  - [Переотправка ссылки](#переотправка-ссылки)
  - [Удаление документа](#удаление-документа)
- [Информация о компании](#информация-о-компании)
- [Платёжные системы](#платёжные-системы)
- [Вебхуки](#вебхуки)
  - [Парсинг событий](#парсинг-событий)
  - [Регистрация обработчиков](#регистрация-обработчиков)
  - [Проверка подписи](#проверка-подписи)
- [Интеграция с FastAPI](#интеграция-с-fastapi)
- [Интеграция с aiogram (телеграм-боты)](#интеграция-с-aiogram-телеграм-боты)
- [Конфигурация клиента](#конфигурация-клиента)
- [Обработка ошибок](#обработка-ошибок)
- [Логирование](#логирование)
- [Внутреннее устройство](#внутреннее-устройство)
- [Разработка и тестирование](#разработка-и-тестирование)
- [Релизы и версионирование](#релизы-и-версионирование)
- [Публикация на PyPI](#публикация-на-pypi)
- [Contributing](#contributing)
- [Лицензия](#лицензия)

---

## Установка

```bash
pip install podpislon-sdk
```

Опциональные «extras»:

```bash
# для готовых FastAPI-помощников
pip install "podpislon-sdk[fastapi]"

# для разработки (тесты, линтеры, type-checking)
pip install "podpislon-sdk[dev]"
```

Поддерживаемые версии Python: **3.9 — 3.13**.

---

## Быстрый старт

```python
import asyncio
from pathlib import Path

from podpislon import PodpislonClient


async def main() -> None:
    async with PodpislonClient(api_key="ВАШ_API_КЛЮЧ") as client:
        # Сколько документов осталось на тарифе?
        info = await client.company.get_info()
        print(f"Компания: {info.company.name}, остаток: {info.signings_left}")

        # Отправить документ на подпись
        result = await client.documents.add(
            name="Иван",
            last_name="Иванов",
            phone="+79991112233",
            files=[Path("contract.pdf")],
        )
        print(f"Создан документ id={result.first_id}")

        # Получить подписанный PDF и сохранить его
        await client.documents.save_file(result.first_id, "signed.pdf")


asyncio.run(main())
```

---

## Аутентификация

Создайте API-ключ в личном кабинете на странице [«Интеграции»](https://podpislon.ru/lk/integrations) и передайте его в клиент:

```python
client = PodpislonClient(api_key="ваш_api_ключ")
```

SDK автоматически добавляет заголовок `X-Api-Key` ко всем исходящим запросам.

> **Совет:** не храните ключ в коде. Используйте переменные окружения и `os.environ["PODPISLON_API_KEY"]`, а в продакшене — менеджер секретов вашей платформы.

---

## Работа с документами

Все эндпоинты «`Document`» доступны через `client.documents`.

### Список документов

```python
page = await client.documents.list(page=1)

print(f"Страница {page.pagination.current_page} из {page.pagination.page_count}")
print(f"Всего документов: {page.pagination.total_count}")

for doc in page:
    print(doc.id, doc.name, doc.status_text)
```

### Постраничный обход

`iter_all` сам обходит все страницы, пока не дойдёт до конца:

```python
async for doc in client.documents.iter_all():
    process(doc)
```

### Фильтрация

```python
from podpislon import DocumentStatus, Filter

page = await client.documents.list(
    filter=Filter(
        status=DocumentStatus.SIGNED,
        fio="Иван Иванов",
        phone="89999999999",
        dates={">=": "1667941200", "<=": "1668041200"},
    ),
    expand="package",  # включить package_id (нужен для resend)
)
```

`DocumentStatus` экспортирует все возможные статусы (`CREATED`, `SENT`, `OPENED`, `SIGNED`, `CANCEL_REQUESTED`, `CANCELLED`) и для каждого даёт человекочитаемое описание:

```python
DocumentStatus.SIGNED.description  # "Подписан"
```

### Отправка документа на подпись

```python
from pathlib import Path
from podpislon import Contact, Payment

result = await client.documents.add(
    name="Иван",
    last_name="Иванов",
    phone="+79991112233",
    files=[Path("contract.pdf"), Path("addendum.pdf")],
    second_name="Иванович",            # опционально
    contacts=[                          # дополнительные подписанты
        Contact(
            name="Пётр",
            last_name="Петров",
            phone="+79111111111",
        ),
    ],
    payment=Payment(pid="2", sum="1200"),
    redirect_url="https://example.com/done",
    sign_by_time=1744035750,            # дедлайн (Unix timestamp)
)

print(result.ids)  # [101, 102]
```

#### Получить ссылку вместо SMS

Передайте `no_sms=True`, чтобы получить готовые ссылки на подписание:

```python
result = await client.documents.add(
    name="Иван",
    last_name="Иванов",
    phone="+79991112233",
    files=[Path("contract.pdf")],
    no_sms=True,
)

for link in result.links:
    print("Подписать:", link)
```

#### JSON вместо multipart

По умолчанию SDK отправляет файлы через `multipart/form-data` (без накладных расходов на base64). Если нужен JSON-режим — передайте `use_multipart=False`:

```python
await client.documents.add(
    name="Иван",
    last_name="Иванов",
    phone="+79991112233",
    files=[b"%PDF-1.4 fake bytes"],
    file_names=["contract.pdf"],
    use_multipart=False,
)
```

### Получение PDF

```python
pdf_bytes = await client.documents.get_file(file_id=101)
Path("signed.pdf").write_bytes(pdf_bytes)

# Или короче:
await client.documents.save_file(101, "signed.pdf")
```

### Переотправка ссылки

```python
await client.documents.resend(
    package_id="cb4b683",     # берётся из document.package при expand="package"
    contact="ODYxMjI=",        # sid конкретного подписанта (опционально)
)
```

### Удаление документа

```python
await client.documents.delete(file_id=101)
```

---

## Информация о компании

```python
info = await client.company.get_info()

print(info.company.name)   # ООО "Рога и копыта"
print(info.company.inn)    # 1001982736
print(info.company.kpp)    # 123456789
print(info.signings_left)  # 259
```

---

## Платёжные системы

```python
systems = await client.payments.list_systems()
for system in systems:
    print(system.id, system.name)
```

---

## Вебхуки

Подпислон отправляет события на ваш URL в формате `application/x-www-form-urlencoded`. SDK даёт типобезопасный парсер и асинхронный диспетчер.

### Парсинг событий

```python
from podpislon import parse_event

event = parse_event(b"EVENT=DOCUMENT_SIGNED&FILE_ID=1234&COMPANY_ID=12&SIGNATURE=abc")
print(event.event)     # WebhookEventType.DOCUMENT_SIGNED
print(event.file_id)   # 1234
```

Поддерживаются все три типа событий из спецификации:

| Событие                              | Модель                              |
| ------------------------------------ | ----------------------------------- |
| `DOCUMENT_OPENED`                    | `DocumentOpenedEvent`               |
| `DOCUMENT_SIGNED`                    | `DocumentSignedEvent`               |
| `CLIENT_DATA_REQUEST_SUBMITTED`      | `ClientDataRequestSubmittedEvent`   |

### Регистрация обработчиков

```python
from podpislon import (
    DocumentOpenedEvent,
    DocumentSignedEvent,
    WebhookEventType,
    WebhookHandler,
)

handler = WebhookHandler()


@handler.on(WebhookEventType.DOCUMENT_SIGNED)
async def signed(event: DocumentSignedEvent) -> None:
    await db.mark_signed(event.file_id)


@handler.on(WebhookEventType.DOCUMENT_OPENED)
async def opened(event: DocumentOpenedEvent) -> None:
    print(f"Документ {event.file_id} открыт телефоном {event.contact}")


@handler.on_any
async def audit(event) -> None:
    await audit_log.write(event)
```

Обработчики могут быть как `async`, так и обычными функциями.

### Проверка подписи

> Алгоритм подписи Подпислона официально не задокументирован. Если служба поддержки сообщит вам нужный алгоритм — передайте его в `compute=`. По умолчанию используется HMAC-SHA256 с секретом из аргумента.

```python
from podpislon import WebhookHandler, WebhookSignatureVerifier

handler = WebhookHandler(
    signature_verifier=WebhookSignatureVerifier(secret="ВАШ_СЕКРЕТ"),
)

# или со своим алгоритмом:
verifier = WebhookSignatureVerifier(
    secret="ВАШ_СЕКРЕТ",
    compute=lambda raw, key: my_custom_signature(raw, key),
)
```

---

## Интеграция с FastAPI

```python
from fastapi import FastAPI, Request, Response, HTTPException
from podpislon import (
    DocumentSignedEvent,
    PodpislonWebhookError,
    WebhookEventType,
    WebhookHandler,
)

app = FastAPI()
handler = WebhookHandler()


@handler.on(WebhookEventType.DOCUMENT_SIGNED)
async def on_signed(event: DocumentSignedEvent) -> None:
    # ваша бизнес-логика
    print("Подписан документ", event.file_id)


@app.post("/webhooks/podpislon")
async def podpislon_webhook(request: Request) -> Response:
    body = await request.body()
    try:
        await handler.dispatch(body, raw_body=body)
    except PodpislonWebhookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=200)
```

И клиент рядом, чтобы инициировать новую отправку:

```python
from contextlib import asynccontextmanager
from podpislon import PodpislonClient

@asynccontextmanager
async def lifespan(app):
    app.state.podpislon = PodpislonClient(api_key=os.environ["PODPISLON_API_KEY"])
    try:
        yield
    finally:
        await app.state.podpislon.aclose()

app = FastAPI(lifespan=lifespan)


@app.post("/contracts/{contract_id}/sign")
async def send_to_sign(contract_id: int, request: Request):
    client = request.app.state.podpislon
    result = await client.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79991112233",
        files=[await render_contract_pdf(contract_id)],
        no_sms=True,
    )
    return {"ids": result.ids, "links": result.links}
```

---

## Интеграция с aiogram (телеграм-боты)

```python
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from podpislon import PodpislonClient

router = Router()
podpislon = PodpislonClient(api_key="...")


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer("Пришлите PDF-документ — отправлю его на подпись.")


@router.message(F.document)
async def send_to_sign(message: Message, bot: Bot) -> None:
    file = await bot.get_file(message.document.file_id)
    pdf_bytes = await bot.download_file(file.file_path)

    result = await podpislon.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79991112233",
        files=[pdf_bytes.read()],
        file_names=[message.document.file_name or "document.pdf"],
        no_sms=True,
    )
    for link in result.links:
        await message.answer(f"Ссылка для подписания: {link}")


async def main() -> None:
    bot = Bot(token="TELEGRAM_BOT_TOKEN")
    dp = Dispatcher()
    dp.include_router(router)
    try:
        await dp.start_polling(bot)
    finally:
        await podpislon.aclose()
        await bot.session.close()
```

---

## Конфигурация клиента

```python
from httpx import Timeout
from podpislon import PodpislonClient

client = PodpislonClient(
    api_key="...",
    base_url="https://podpislon.ru/integration",  # переопределить редко нужно
    timeout=Timeout(30.0, connect=5.0),
    max_retries=3,                                # ретраи 429/5xx с экспоненциальной паузой
    rate_limit=4,                                 # клиентская защита (4 RPS)
    user_agent="my-app/1.2.3",
)
```

Если у вас уже есть свой `httpx.AsyncClient` (например, c прокси или mTLS), передайте его в `http_client=`:

```python
import httpx
from podpislon import PodpislonClient

shared = httpx.AsyncClient(proxies="http://proxy:3128")
client = PodpislonClient(api_key="...", http_client=shared)
# ВАЖНО: при пользовательском http_client SDK НЕ закроет его сам.
```

---

## Обработка ошибок

Все исключения наследуются от `PodpislonError`:

```python
from podpislon import (
    PodpislonAuthenticationError,    # HTTP 401
    PodpislonPermissionError,        # HTTP 403
    PodpislonNotFoundError,          # HTTP 404
    PodpislonRateLimitError,         # HTTP 429 после исчерпания ретраев
    PodpislonServerError,            # HTTP 5xx
    PodpislonAPIError,               # любой иной API-ответ с ошибкой
    PodpislonValidationError,        # ошибка валидации параметров на стороне клиента
    PodpislonTransportError,         # таймаут / сеть / DNS
    PodpislonError,                  # базовый класс
)

try:
    await client.documents.delete(123)
except PodpislonNotFoundError:
    print("Документ не найден")
except PodpislonAuthenticationError:
    print("Неверный API-ключ")
except PodpislonError as exc:
    print(f"Что-то пошло не так: {exc}")
```

У `PodpislonAPIError` есть полезные атрибуты: `status_code`, `response_body`, `request_id`.

---

## Логирование

SDK пишет отладочные сообщения в стандартный модуль `logging` под именем `podpislon`:

```python
import logging
logging.getLogger("podpislon").setLevel(logging.DEBUG)
```

---

## Внутреннее устройство

```
podpislon/
├── client.py              # PodpislonClient — фасад
├── _transport.py          # httpx-обёртка: rate limit, ретраи, маппинг ошибок
├── _utils.py              # rate-limiter, base64, form-encoding helpers
├── exceptions.py          # иерархия PodpislonError
├── enums.py               # DocumentStatus, WebhookEventType
├── models/                # pydantic v2 модели
├── resources/             # Documents / Company / Payments
└── webhooks/              # parser + handler + signature verifier
```

Ключевые свойства:

* **Async-first.** Под капотом `httpx.AsyncClient`. Никаких блокирующих вызовов на горячем пути.
* **Type-safe.** Pydantic v2 для всех моделей, экспортируется `py.typed` маркер.
* **Rate-limiter из коробки.** Скользящее окно 4 RPS на ключ — соответствует ограничению API.
* **Ретраи с экспоненциальным backoff** на `429` и `5xx`, с уважением к заголовку `Retry-After`.
* **Никаких глобальных стейтов.** Один клиент = один пул соединений; легко работать с несколькими ключами одновременно.
* **Webhook-handler.** Декораторный API в духе `aiogram`.

---

## Разработка и тестирование

```bash
git clone https://github.com/IceOne-i/podpislon-sdk.git
cd podpislon-sdk

python -m venv .venv
source .venv/bin/activate           # Linux / macOS
# .venv\Scripts\activate            # Windows

pip install -e ".[dev]"

# тесты с покрытием
pytest --cov=podpislon

# линт и формат
ruff check src tests
ruff format src tests

# type-checking
mypy src
```

---

## Релизы и версионирование

Версии собираются автоматически из git-тегов с помощью `hatch-vcs`. Чтобы выпустить новую версию:

```bash
git tag v1.2.3
git push origin v1.2.3
```

GitHub Actions подхватит тег, соберёт `sdist` + `wheel` и опубликует пакет на PyPI (см. workflow ниже).

Соблюдается [SemVer](https://semver.org/lang/ru/):

* `MAJOR` — несовместимые изменения публичного API;
* `MINOR` — обратносовместимые новые возможности;
* `PATCH` — обратносовместимые исправления.

---

## Публикация на PyPI

В репозитории два workflow:

1. `.github/workflows/tests.yml` — на каждый PR/push прогоняет тесты на Python 3.9 — 3.13.
2. `.github/workflows/publish.yml` — на каждый push тега `v*` собирает дистрибутивы и публикует их на PyPI через [Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (без хранения токенов в репозитории).

Чтобы включить публикацию:

1. Зарегистрируйте проект на PyPI (`pypi.org/manage/account/publishing/`) — добавьте Trusted Publisher с owner = `IceOne-i`, repo = `podpislon-sdk`, workflow = `publish.yml`, environment = `pypi`.
2. В GitHub-репозитории создайте окружение `pypi` (Settings → Environments).
3. Запушьте тег `vX.Y.Z` — workflow сработает сам.

Если вы предпочитаете API-токен вместо Trusted Publishing, добавьте в секреты репозитория `PYPI_API_TOKEN` и раскомментируйте соответствующий шаг в `publish.yml`.

---

## Contributing

Pull requests welcome! Но прежде чем большой PR — заведите issue с обсуждением.

1. Форкните репозиторий и создайте ветку.
2. Установите dev-зависимости: `pip install -e ".[dev]"`.
3. Добавьте тесты на новый функционал.
4. Прогоните `pytest`, `ruff`, `mypy`.
5. Откройте PR с осмысленным описанием.

---

## Лицензия

[MIT](LICENSE) — самая разрешительная из распространённых лицензий. Можно использовать в коммерческих и закрытых проектах при условии сохранения исходного уведомления об авторских правах. Подробнее в файле [LICENSE](LICENSE).

---

## Полезные ссылки

* Сайт сервиса (не аффилирован с этим SDK): <https://podpislon.ru/>
* OpenAPI спецификация: <https://api.podpislon.ru/podpislon-api.yaml>
* Личный кабинет → Интеграции: <https://podpislon.ru/lk/integrations>
* Issues / запросы: <https://github.com/IceOne-i/podpislon-sdk/issues>
