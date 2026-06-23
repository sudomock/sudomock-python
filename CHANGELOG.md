# Changelog

All notable changes to the `sudomock` Python SDK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `Mockup.thumbnail` field, documenting the 720px main thumbnail returned by
  `psd.upload`, `mockups.list`, and `mockups.get`.

### Changed
- `renders.create_video` now validates and serializes its animation options
  through the typed `VideoOptions` model (single source of truth) instead of an
  inline dict.
- Clarified that `max_retries` is the *total* number of request attempts
  (initial request + retries), not the number of extra retries.

### Removed
- Unused `ApiResponse` model (it was never returned or exported).
- `export_label` parameter from `renders.create_video` (the video render
  endpoint has no such field; `renders.create` still accepts it).

## [0.2.0] - 2026-06-24

### Added
- Async server-side render queue: `renders.create(..., is_async=True)` returns a
  `JobAccepted` (HTTP 202).
- `jobs` resource: `list`, `get`, and `wait` for polling async jobs.
- AI video rendering via `renders.create_video` (render mode and raw-image mode).
- PSD upload via `psd.upload` (sync `Mockup` or async `JobAccepted`).
- Webhook endpoint management (`webhook_endpoints`: create / list / get / update /
  delete / rotate_secret / test / deliveries / events / replay) and inbound
  signature verification (`verify_webhook_signature`).

### Changed
- Aligned `Job`, webhook models, and the signature helper to the real backend
  routes; bare (non-enveloped) backend responses are now parsed correctly.
- Renamed the async-job identifier from `render_uuid` to `job_id` (the synchronous
  still-render id remains `render_uuid`).

## [0.1.0] - 2026-03-22

### Added
- Initial Python SDK with synchronous (`SudoMock`) and asynchronous
  (`AsyncSudoMock`) clients.
- Mockup listing/detail, still renders, SudoAI 2D rendering, account/usage, and
  packages/pricing lookups.
- Typed Pydantic v2 response models, typed exceptions, and tenacity-backed retry
  with exponential backoff.

[Unreleased]: https://github.com/sudomock/sudomock-python/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/sudomock/sudomock-python/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/sudomock/sudomock-python/releases/tag/v0.1.0
