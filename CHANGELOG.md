# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions are derived automatically from git tags (`vX.Y.Z`) using `hatch-vcs`.

## [Unreleased]

### Fixed
- `CompanyInfo.signings` and `Company.inn` / `Company.kpp` now accept
  integer payloads from the live API, not just strings — the production
  endpoint was observed returning `signings: 10` instead of `"10"`. The
  base model now sets `coerce_numbers_to_str=True`, and `signings`
  additionally has an explicit pre-validator.

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
