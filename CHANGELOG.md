# Changelog

All notable changes to the Kapman Trading System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial database schema with TimescaleDB hypertables
- Core tables: `tickers`, `portfolios`, `ohlcv_daily`, `daily_snapshots`
- Basic portfolio management functionality

## [0.2.0] - 2025-12-09
### Added
- **Story 2.0: Enhanced Metrics Schema (Migration 004)**
  - Added 45+ technical, dealer, and volatility metrics to `daily_snapshots`
  - Created `options_daily_summary` hypertable for options data
  - Implemented Wyckoff event tracking views:
    - `v_wyckoff_events`: Base view for all Wyckoff events
    - `v_entry_signals`: Filtered view for entry signals (SPRING, SOS)
    - `v_exit_signals`: Filtered view for exit signals (BC with score ≥ 24)
  - Added universe tracking to `tickers` table
  - Implemented data retention policies

### Changed
- Updated database schema to support Sprint 2 features
- Optimized indexes for Wyckoff pattern detection queries

### Fixed
- Resolved view dependency issues
- Fixed data type inconsistencies in schema

## [0.1.0] - 2025-11-15
### Added
- Initial project setup
- Basic database schema
- Core infrastructure components

[Unreleased]: https://github.com/yourusername/kapman-trader/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/yourusername/kapman-trader/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yourusername/kapman-trader/releases/tag/v0.1.0
