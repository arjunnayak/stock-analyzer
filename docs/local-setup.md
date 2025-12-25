# Local Development Setup

This guide will help you set up the complete local development environment for the Stock Analyzer project.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.10+
- `uv` package manager (or pip)

## Quick Start

### 1. Start Local Services

```bash
# Start all services (Postgres, MinIO, Supabase Studio)
docker compose up -d

# Check service health
docker compose ps
```

Expected services:
- **PostgreSQL** - `localhost:5432` (database)
- **Supabase Studio** - `localhost:54323` (database UI)
- **PostgREST API** - `localhost:54321` (REST API)
- **MinIO** - `localhost:9000` (S3-compatible storage)
- **MinIO Console** - `localhost:9001` (storage UI)

### 2. Verify Services

```bash
# Check database is ready
docker compose exec postgres psql -U postgres -c "SELECT version();"

# Check MinIO bucket was created
docker compose logs minio-setup
```

### 3. Install Python Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

## Service Details

### PostgreSQL/Supabase

**Connection Details:**
- Host: `localhost`
- Port: `5432`
- Database: `postgres`
- User: `postgres`
- Password: `postgres`
- Connection String: `postgresql://postgres:postgres@localhost:5432/postgres`

**Supabase Studio (Web UI):**
- URL: http://localhost:54323
- View and manage database tables, run queries, inspect data

**PostgREST API:**
- URL: http://localhost:54321
- Auto-generated REST API for all database tables

### MinIO (Local R2/S3)

**Connection Details:**
- Endpoint: `http://localhost:9000`
- Access Key: `minioadmin`
- Secret Key: `minioadmin`
- Bucket: `market-data`
- Region: `us-east-1`

**MinIO Console (Web UI):**
- URL: http://localhost:9001
- Login: `minioadmin` / `minioadmin`
- Browse buckets, upload files, manage objects

## Database Schema

The initial migration (`001_initial_schema.sql`) creates:

### Core Tables

1. **users** - User accounts and preferences
   - `id`, `email`, `investing_style`, `alerts_enabled`

2. **entities** - Stock/ticker metadata
   - `id`, `ticker`, `name`, `sector`
   - Tracks data availability and date ranges

3. **watchlists** - User watchlists (many-to-many)
   - Links users to entities they're monitoring

4. **user_entity_settings** - Stateful monitoring data
   - Stores previous signal states per user/stock
   - Critical for "material change" detection

5. **alert_history** - Alert delivery tracking
   - Records all alerts sent to users

### Test Data

The migration includes test data:
- 2 test users: `test@example.com`, `value@example.com`
- 5 stocks: AAPL, MSFT, GOOGL, TSLA, NVDA
- Test user has all 5 stocks in their watchlist

## Working with the Database

### Using psql (CLI)

```bash
# Connect to database
docker compose exec postgres psql -U postgres

# List tables
\dt

# Query users
SELECT * FROM users;

# Query entities
SELECT * FROM entities;

# Exit
\q
```

### Using Supabase Studio (Web UI)

1. Open http://localhost:54323
2. Navigate to "Table Editor" to view/edit data
3. Use "SQL Editor" to run queries

### Running Migrations

Migrations are automatically run when the database first starts.

To re-run migrations:

```bash
# Stop and remove volumes
docker compose down -v

# Start fresh (migrations will run automatically)
docker compose up -d
```

To add new migrations:

```bash
# Create new migration file
touch supabase/migrations/002_your_migration.sql

# Restart database to apply
docker compose restart postgres
```

## Working with MinIO (Local R2)

### Using MinIO Console (Web UI)

1. Open http://localhost:9001
2. Login with `minioadmin` / `minioadmin`
3. Navigate to `market-data` bucket
4. Upload/download files

### Using Python (boto3)

```python
import boto3

# Create S3 client pointing to MinIO
s3 = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin',
    region_name='us-east-1'
)

# List buckets
response = s3.list_buckets()
print(response['Buckets'])

# Upload a file
s3.upload_file('local_file.json', 'market-data', 'prices/v1/AAPL/2024/01/data.parquet')

# Download a file
s3.download_file('market-data', 'prices/v1/AAPL/2024/01/data.parquet', 'local_file.parquet')
```

### R2 Storage Layout (from architecture)

```
market-data/
├── prices/v1/{ticker}/{year}/{month}/data.parquet
├── fundamentals/v1/{ticker}/{year}/{month}/data.parquet
├── signals_valuation/v1/{ticker}/{year}/{month}/data.parquet
└── signals_technical/v1/{ticker}/{year}/{month}/data.parquet
```

## Environment Variables

The `.env.local` file is configured to use local services by default:

```bash
ENV=LOCAL  # Uses LOCAL_* variables

# To switch to remote/production:
ENV=REMOTE  # Uses REMOTE_* variables
```

Your application code should read the `ENV` variable and select the appropriate credentials.

## Common Tasks

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f postgres
docker compose logs -f minio
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart postgres
```

### Stop Services

```bash
# Stop (keeps data)
docker compose stop

# Stop and remove (keeps volumes)
docker compose down

# Stop and remove everything (INCLUDING DATA)
docker compose down -v
```

### Connect to Service Container

```bash
# Postgres
docker compose exec postgres bash

# MinIO
docker compose exec minio sh
```

## Troubleshooting

### Port Already in Use

If ports are already in use, you can change them in `docker-compose.yml`:

```yaml
ports:
  - "5433:5432"  # Changed from 5432:5432
```

### Database Migration Issues

```bash
# Check migration logs
docker compose logs postgres

# Manually run migrations
docker compose exec postgres psql -U postgres -f /docker-entrypoint-initdb.d/001_initial_schema.sql
```

### MinIO Bucket Not Created

```bash
# Check setup logs
docker compose logs minio-setup

# Manually create bucket
docker compose exec minio mc mb /data/market-data
```

### Reset Everything

```bash
# Nuclear option - delete all data and start fresh
docker compose down -v
docker compose up -d
```

## Next Steps

1. ✅ Local infrastructure is running
2. 📊 Start developing data ingestion pipeline
3. 🔍 Build signal computation logic
4. 📧 Implement alert system

See the main project documentation for implementation details:
- `docs/mvp-product-plan.md` - Product requirements
- `docs/system-architecture.md` - Technical architecture
- `docs/storage-architecture.md` - R2 storage design
- `docs/ingest.md` - Data ingestion guide (if exists)
