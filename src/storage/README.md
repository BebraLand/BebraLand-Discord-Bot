# Database Storage

This module provides a unified SQLAlchemy-based storage system for the Discord bot.

## Features

- **Unified ORM**: Single SQLAlchemy implementation supports multiple databases
- **Async Support**: Built on SQLAlchemy's async capabilities for non-blocking database operations
- **Multiple Databases**: Supports SQLite, PostgreSQL, MySQL, and MariaDB
- **Auto-migrations**: Tables are automatically created on startup

## Supported Databases

### SQLite (Default)
Best for development and small deployments.
```
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```

### PostgreSQL
Best for production deployments.
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/bot_db
```

For cloud databases requiring SSL (e.g., Supabase, AWS RDS):
```
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db?ssl=require
```

Or using individual parameters:
```env
DB_TYPE=postgresql
DB_HOST=db.example.supabase.co
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=postgres
DB_SSL_MODE=require
```

### MySQL/MariaDB
Alternative production option.
```
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/bot_db
```

## Configuration

### Option 1: DATABASE_URL (Recommended)
Set the full connection URL:
```env
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
```

### Option 2: Individual Parameters
Alternatively, set individual connection parameters:
```env
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=bot_user
DB_PASSWORD=secure_password
DB_NAME=bot_db
```

For SQLite:
```env
DB_TYPE=sqlite
DB_PATH=data/bot.db
```

## Tables

### user_languages
Stores user language preferences.
- `user_id` (VARCHAR, PRIMARY KEY)
- `language` (VARCHAR)

### scheduled_tasks
Stores scheduled bot tasks.
- `id` (INTEGER, PRIMARY KEY)
- `type` (VARCHAR)
- `guild_id` (BIGINT)
- `channel_id` (BIGINT)
- `time` (VARCHAR)
- `run_at` (FLOAT)
- `payload` (TEXT, JSON)

### tickets
Stores support tickets.
- `id` (INTEGER, PRIMARY KEY)
- `user_id` (VARCHAR)
- `issue` (TEXT)
- `channel_id` (BIGINT)
- `status` (VARCHAR)
- `created_at` (FLOAT)
- `closed_at` (FLOAT)

## Dependencies

Install the required packages:
```bash
pip install -r requirements-db.txt
```

This includes:
- `sqlalchemy>=2.0.0` - ORM framework
- `aiosqlite>=0.20.0` - SQLite async driver
- `asyncpg>=0.30.0` - PostgreSQL async driver
- `aiomysql>=0.3.0` - MySQL/MariaDB async driver

## Migration from Old System

The old system used separate implementations for each database type. The new system:
- Uses a single SQLAlchemy-based implementation
- Automatically handles database-specific syntax differences
- Provides better connection pooling and error handling
- Includes all ticket management methods across all database types
