cat > db/README.md << 'EOF'
# Kapman Trading System - Database

This directory contains database migrations and schema definitions for the Kapman Trading System.

## Schema Overview

### Core Tables
- `portfolios` - Trading portfolios
- `tickers` - Stock symbols and metadata
- `portfolio_tickers` - Many-to-many relationship between portfolios and tickers

### Time-Series Data (TimescaleDB Hypertables)
- `ohlcv_daily` - Daily OHLCV data
- `options_chains` - Options market data
- `daily_snapshots` - Wyckoff analysis results

### Trading
- `recommendations` - Generated trade recommendations
- `recommendation_outcomes` - Track performance of recommendations

## Migrations

Migrations are applied in numerical order. The current migrations are:

1. `0001_initial_schema` - Core database schema
2. `0002_compression_retention` - TimescaleDB compression and retention policies
3. `0003_initial_data` - Initial portfolio and ticker data

## Running Migrations

Migrations are automatically applied when the database container starts. The `db` service in docker-compose.yml is configured to run all SQL files in the `db/migrations` directory in alphabetical order.

To manually apply migrations, you can use the `apply_migrations.sh` script:

```bash
# Make the script executable
chmod +x db/apply_migrations.sh

# Run the script
./db/apply_migrations.sh
