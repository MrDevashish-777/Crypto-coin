#!/bin/bash
# Wait for PostgreSQL to be ready
until pg_isready -h postgres -U crypto_user; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

# Create the database if it doesn't exist
psql -h postgres -U crypto_user -d postgres -c "CREATE DATABASE crypto_bot_dev;" || echo "Database already exists"

echo "Database setup complete"