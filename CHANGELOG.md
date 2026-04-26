# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions are derived automatically from git tags (`vX.Y.Z`) using `hatch-vcs`.

## [Unreleased]

### Fixed
- **Retry policy no longer duplicates documents on transient failures.**
  `client.documents.add` is now marked non-idempotent (`idempotent=False`)
  even though the API uses `PUT`, because every successful call creates a
  new draft on Podpislon's side. With the old policy a 5xx or read-timeout
  would trigger up to 3 retries, silently spawning duplicate drafts and
  burning the customer's signing balance. The transport layer now follows
  RFC 7231 retry semantics by default:
  * idempotent methods (GET / HEAD / OPTIONS / PUT / DELETE) — full retry on
    network errors, 5xx, 429;
  * POST / PATCH / explicitly-marked non-idempotent calls — retry only on
    connect-side errors and on `408` / `425` / `429` (statuses that prove
    the server never processed the request);
  * 5xx and read-timeouts on non-idempotent calls surface immediately.

  `client.documents.resend` is also marked non-idempotent (the API sends an
  SMS on every successful call). Pass `retry_non_idempotent=True` to
  `PodpislonClient` to opt back into the legacy behaviour if you have your
  own duplicate detection.
- `CompanyInfo.signings` and `Company.inn` / `Company.kpp` now accept
  integer payloads from the live API, not just strings — the production
  endpoint was observed returning `signings: 10` instead of `"10"`. The
  base model now sets `coerce_numbers_to_str=True`, and `signings`
  additionally has an explicit pre-validator.

### Added
- `PodpislonClient(retry_non_idempotent=True)` — opt-in flag that restores
  the previous "retry every transient failure" behaviour for callers with
  their own idempotency-key tracking.
- `RetryPolicy.should_retry_status` / `should_retry_exception` — building
  blocks for custom retry policies.

### Added
- First public release of the unofficial async Python SDK for Podpislon.
- `PodpislonClient` async client with resource accessors:
  - `client.documents` — list / add / get-file / resend / delete
  - `client.company` — get-info
  - `client.payments` — list-systems
- Pydantic v2 models for all API entities (Document, Contact, Company, Payment, …).
- Built-in client-side rate limiter (4 RPS per key, matches the API limit).
- Configurable retries for `429` and `5xx` responses with exponential backoff.
- Async iteration helper `client.documents.iter_all()` for paginated document listing.
- Webhook handler with type-safe event dispatch (`DOCUMENT_OPENED`,
  `DOCUMENT_SIGNED`, `CLIENT_DATA_REQUEST_SUBMITTED`).
- FastAPI integration helper for receiving webhooks.
- Examples for FastAPI and aiogram bots.
