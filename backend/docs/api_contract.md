# Health API Contract

## `GET /api/health`

- Purpose: basic application liveness check.
- Success response:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "running",
    "database": "connected",
    "app": "..."
  }
}
```

## `GET /api/health/db`

- Purpose: validate the current database connection with `SELECT 1`.
- Success response:

```json
{
  "success": true,
  "message": "ok",
  "data": {
    "status": "connected",
    "dialect": "sqlite",
    "database_url_masked": "sqlite:///./schema/supply_chain.db",
    "preferred_database_url_masked": "mysql+pymysql://root:***@127.0.0.1:2881/supply_chain?charset=utf8mb4",
    "mode": "sqlite-fallback",
    "preferred_backend": "oceanbase"
  }
}
```

- `dialect`: SQLAlchemy-reported database dialect, such as `sqlite` or `mysql`.
- `database_url_masked`: the active database URL with password hidden.
- `preferred_database_url_masked`: the preferred primary database URL with password hidden.
- `mode`: `oceanbase-primary` when the main OceanBase connection is active, or `sqlite-fallback` when the app automatically falls back to SQLite.
- `preferred_backend`: current primary backend target; in this project it is `oceanbase`.
- Failure response:

```json
{
  "success": false,
  "message": "database connection failed: <ExceptionType>",
  "data": null
}
```

- Failure responses keep the existing unified response format and do not expose plaintext passwords.
