#!/bin/bash
set -e

# Load environment variables
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
fi

# Default values
DB_USER=${DB_USER:-kapman}
DB_NAME=${DB_NAME:-kapman}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}

# Check if psql is installed
if ! command -v psql &> /dev/null; then
    echo "Error: psql is not installed. Please install PostgreSQL client tools."
    exit 1
fi

# Function to run a migration
run_migration() {
    local migration_file=$1
    echo "Applying migration: $migration_file"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f "$migration_file"
}

# Get list of migration files
MIGRATION_FILES=($(ls -1v migrations/*.sql))

# Apply each migration
for file in "${MIGRATION_FILES[@]}"; do
    run_migration "$file"
done

echo "All migrations applied successfully."
