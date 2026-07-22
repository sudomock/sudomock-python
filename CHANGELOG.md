# Changelog

All notable changes to the `sudomock` Python SDK are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-07-23

### Added

- PSD text personalization through `renders.create(text_layers=...)` on both
  synchronous and asynchronous clients. Single-style text, styled segments,
  font, size, color, outline color, and fit controls are supported.
- Typed text-layer metadata on mockup/upload responses and font details on
  render responses.
- Successful response warnings and backend `error_code` values are surfaced.

### Changed

- `smart_objects` is optional for text-only renders. Existing keyword calls are
  unchanged.

## [0.5.1] - 2026-07-21

### Added
- `ai.render()` accepts an optional `is_async` flag (mirrors `ai.create()`).
  Default `False` keeps the synchronous `200` behaviour (returns the finished
  `AIRender`). Pass `is_async=True` to submit to the server-side queue and get a
  `JobAccepted` (`202`, `kind="2d_render"`) to poll with `jobs.get()` /
  `jobs.wait()`; the terminal `Job` carries `result_url`. Additive and
  non-breaking — the mockup id stays in the path and existing call sites are
  unaffected.

## [0.5.0] - 2026-07-21

### Changed (BREAKING)
- `ai.create()` is now **synchronous by default**: it returns the finished
  `TwoDMockup` from the `201` response instead of always returning a
  `JobAccepted`. Pass `is_async=True` to submit to the server-side queue and get
  a `JobAccepted` (`202`) to poll with `wait_for_2d_mockup()`. Callers that
  relied on `create()` always returning a job must either read the returned
  `TwoDMockup` directly or opt in with `is_async=True`.
- 2D mockup endpoints moved to canonical **plural** paths: `get`, `delete`,
  `update_2d_print_areas`, and `render` now target `/api/v1/sudoai/2d-mockups/...`
  (the singular `/2d-mockup/...` paths are gone). This is a hard break on
  `0.4.1`, whose transport does not follow redirects.
- `ai.render()` now takes the mockup id in the **path**
  (`/2d-mockups/{mockup_uuid}/render`); `mockup_uuid` is no longer sent in the
  request body. The render call signature (`mockup_uuid=`, `print_areas=`,
  `export_options=`) is unchanged.

### Added
- `ai.create()` accepts an optional `print_areas` seed (four-point quads, each
  with an optional `name`).
- `Quad.name` -- print areas can now carry a human-readable name (from
  create/get/list `quads` and `update_2d_print_areas`).
- `AIRender.render_uuid` -- the render transaction id is now surfaced (a sibling
  of `print_files` in the render `data` envelope).

## [0.3.0] - 2026-06-24

### Added
- `Mockup.thumbnail` field, documenting the 720px main thumbnail returned by
  `psd.upload`, `mockups.list`, and `mockups.get`.

### Changed
- The async job identifier is now `job_id` everywhere (202 accept, job poll, and
  webhook delivery); `WebhookDelivery.job_uuid` is now `WebhookDelivery.job_id`,
  matching the SudoMock API contract. The synchronous render's `render_uuid` is
  unchanged (it is the render's transaction id, a distinct concept).
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
