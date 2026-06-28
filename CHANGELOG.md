# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-27
### Changed
- Default token storage backend changed from `keyring` to `auto`. The `auto` backend dual-writes tokens to both the OS keyring (best-effort) and a local file with `0600` permissions. On read, it tries keyring first and falls back to the file, fixing `not_authenticated` errors in non-interactive and sandboxed environments.

### Added
- New `auto` option for `--token-storage` in `ghealth auth configure`.

## [1.0.0] - 2026-06-26
### Added
- Complete command line support for all Google Health REST API resources (Identity, Profile, Settings, Devices, Data Points, Webhook Subscribers, and Subscriptions).
- Secure local token storage using OS Credential Store / Keyring.
- Automatic silent refresh of Google Health access tokens.
- Native tabular formatting for humans and deterministic `--format json` output for AI agents.
- Convenient CLI shortcuts for common queries: `steps`, `sleep`, `calories`, `heart-rate`, `weight`, `nutrition`, and more.
- Static G Health data types registry with operation and scope discovery.
- Offline-first design and comprehensive mocked CLI integration test suite.
