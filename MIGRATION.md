# Migration Guide: SQLAlchemy Storage

This guide helps you migrate from the old custom storage system to the new SQLAlchemy-based implementation.

## What Changed?

### Old System
- Separate implementations for SQLite, PostgreSQL, and MySQL
- Manual SQL queries for each operation
- Incomplete ticket support in PostgreSQL and MySQL
- Different APIs for each database type

### New System
- Single unified SQLAlchemy implementation
- ORM-based with automatic query generation
- Complete feature parity across all databases
- Built-in connection pooling and migrations

## Installation

Install the required dependencies:

```bash
pip install sqlalchemy>=2.0.0 aiosqlite>=0.20.0 asyncpg>=0.30.0 aiomysql>=0.3.0
```

Or use the requirements file:

```bash
pip install -r requirements-db.txt
```

## Environment Variables

### Old Format (Deprecated)
```env
STORAGE_TYPE=postgresql
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://user:pass@host/db
DB_DRIVER=postgresql
```

### New Format (Recommended)

**Option 1: Use DATABASE_URL**
```env
# SQLite (default)
DATABASE_URL=sqlite+aiosqlite:///data/bot.db

# PostgreSQL (local)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/bot_db

# PostgreSQL (cloud with SSL - e.g., Supabase, AWS RDS)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db?ssl=require

# MySQL/MariaDB
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/bot_db
```

**Option 2: Use Individual Parameters**
```env
# PostgreSQL (local)
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=bot_user
DB_PASSWORD=secure_password
DB_NAME=bot_db

# PostgreSQL (cloud with SSL - e.g., Supabase)
DB_TYPE=postgresql
DB_HOST=db.example.supabase.co
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password
DB_NAME=postgres
DB_SSL_MODE=require

# MySQL
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=secret
DB_NAME=bot_db

# SQLite
DB_TYPE=sqlite
DB_PATH=data/bot.db
```

## Database URL Format

The new system uses SQLAlchemy async drivers:

| Database | Old URL | New URL |
|----------|---------|---------|
| SQLite | `sqlite:///path.db` | `sqlite+aiosqlite:///path.db` |
| PostgreSQL | `postgresql://user:pass@host/db` | `postgresql+asyncpg://user:pass@host/db` |
| MySQL | `mysql://user:pass@host/db` | `mysql+aiomysql://user:pass@host/db` |
| MariaDB | `mariadb://user:pass@host/db` | `mysql+aiomysql://user:pass@host/db` |

**Note:** The factory will automatically convert old URL formats to new ones, so existing URLs will continue to work.

## Data Migration

### SQLite Users
No migration needed! The table schemas are identical. Just update your environment variables and restart the bot.

### PostgreSQL Users
1. Update your environment variables to use the new format
2. The tables will be automatically created on first run
3. If you have existing data, run this SQL to verify compatibility:

```sql
-- Check existing tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';

-- The new system creates the same tables:
-- - user_languages
-- - scheduled_tasks
-- - tickets
```

### MySQL/MariaDB Users
1. Update your environment variables to use the new format
2. Tables will be automatically created on first run
3. Existing tables are compatible with the new system

## Backward Compatibility

The new system maintains backward compatibility:

- ✅ All existing `LanguageStorage` protocol methods work identically
- ✅ All existing `TicketStorage` protocol methods work identically
- ✅ Legacy environment variables are still supported (STORAGE_TYPE, DATABASE_TYPE)
- ✅ Old database URL formats are automatically converted
- ✅ Existing database schemas are compatible

## Testing Your Migration

1. Update your `.env` file with the new format
2. Install the new dependencies
3. Start your bot
4. Check the logs for successful initialization:
   ```
   SQLAlchemy storage initialized with sqlite+aiosqlite
   Language manager initialized
   ```

## Troubleshooting

### "No module named 'sqlalchemy'"
Install the dependencies:
```bash
pip install -r requirements-db.txt
```

### "No module named 'aiosqlite'"
Install the SQLite driver:
```bash
pip install aiosqlite
```

### "No module named 'asyncpg'" (PostgreSQL)
Install the PostgreSQL driver:
```bash
pip install asyncpg
```

### "No module named 'aiomysql'" (MySQL/MariaDB)
Install the MySQL driver:
```bash
pip install aiomysql
```

### Database connection errors
1. Check your DATABASE_URL or DB_* environment variables
2. Verify your database server is running
3. Check firewall and network connectivity
4. Ensure database user has proper permissions

### "[Errno 11001] getaddrinfo failed" (DNS resolution error)
This error occurs when the bot cannot resolve the database hostname:
1. **Check your internet connection** - Ensure the bot has internet access
2. **Verify the hostname** - Make sure DB_HOST is correct (e.g., `db.example.supabase.co`)
3. **Try with IP address** - If DNS is blocked, use the database's IP address instead
4. **Check DNS servers** - Ensure your system can resolve external domains
5. **Firewall/Network** - Check if your network blocks database connections

For cloud databases (Supabase, AWS RDS, etc.):
- Ensure SSL mode is set: `DB_SSL_MODE=require` or add `?ssl=require` to DATABASE_URL
- Check if the database allows connections from your IP address
- Verify credentials are correct (user, password, database name)

### Cloud Database SSL Requirements (Supabase, AWS RDS, etc.)
If connecting to Supabase or other cloud databases:
```env
# Option 1: DATABASE_URL with SSL
DATABASE_URL=postgresql+asyncpg://postgres.xxx:password@aws-x-region.pooler.supabase.com:6543/postgres?ssl=require

# Option 2: Individual parameters
DB_TYPE=postgresql
DB_HOST=aws-x-region.pooler.supabase.com
DB_PORT=6543
DB_USER=postgres.xxx
DB_PASSWORD=your_password
DB_NAME=postgres
DB_SSL_MODE=require
```

**Note:** For Supabase Transaction/Session Pooler, use the pooler hostname and port instead of the direct connection.

### Tables not created
The new system automatically creates tables on initialization. If tables aren't created:
1. Check bot logs for errors
2. Verify database user has CREATE TABLE permissions
3. For PostgreSQL/MySQL, ensure the database exists

## Rollback

If you need to rollback to the old system:

1. Checkout the previous commit:
   ```bash
   git checkout <previous-commit-hash>
   ```

2. Reinstall old dependencies if needed

3. Restart your bot

## Support

For issues or questions about the migration:
1. Check the [Storage README](README.md) for detailed documentation
2. Open an issue on GitHub
3. Review the test files (`test_storage.py`, `test_config.py`) for examples

## Benefits of Migrating

- 🚀 **Better Performance**: Connection pooling and optimized queries
- 🔒 **Enhanced Security**: ORM prevents SQL injection
- 🛠️ **Easier Maintenance**: Single codebase for all databases
- ✨ **More Features**: Complete ticket support on all databases
- 📊 **Better Monitoring**: Built-in query logging and metrics
- 🔄 **Future-Proof**: Easy to add new features and tables
