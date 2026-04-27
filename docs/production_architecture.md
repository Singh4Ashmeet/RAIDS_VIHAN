# Production Architecture - RAID Nexus

## Current State (Prototype)

RAID Nexus currently runs as a prototype-oriented FastAPI application with a single application process and in-process CPU computation for benchmark, fairness, dispatch scoring, and demand prediction tasks. Local development can use SQLite through `aiosqlite`; hosted deployments can use PostgreSQL through `asyncpg` when `DATABASE_URL` is configured. This architecture is appropriate for development, demonstrations, and hackathon-scale evaluation because it keeps deployment simple. It is not intended to represent the full production scalability envelope of the system.

## Production Target Architecture

```text
      [Load Balancer (nginx)]
               |
          +----+----+
          | FastAPI |  x3 processes (uvicorn workers)
          | async   |
          +----+----+
               |
    +----------+--------------+
    |          |              |
    v          v              v
[PostgreSQL] [Redis]    [Celery Workers]
[asyncpg    ] [cache ]  [demand_predictor]
[pool: 10   ] [WS    ]  [benchmark       ]
[connections] [pubsub] [fairness compute]
```

## Migration Path

1. Database: SQLite fallback or prototype Postgres -> managed PostgreSQL 15+ with formal Alembic migrations. This provides durable concurrent writes, transactional robustness, and connection pooling needed for multi-worker operation.
2. Workers: in-process tasks -> Celery 5 with Redis broker. This isolates CPU-heavy workloads from request-serving processes and makes demand prediction, benchmarking, and fairness computation horizontally scalable.
3. WebSocket: single-server broadcast -> Redis Pub/Sub fanout. This allows WebSocket-connected clients to receive consistent live updates even when requests are handled by different FastAPI instances.
4. Caching: in-memory dict caches -> Redis with TTL. This ensures route, traffic, density-grid, and benchmark caches survive process restarts and remain shared across server instances.

## Estimated Capacity

| Component | Current Limit | Production Target |
|---|---:|---:|
| Concurrent WebSocket clients | ~50 | 10,000+ |
| Dispatches per minute | ~10 | 500+ |
| Database connections | 1 SQLite connection or small prototype Postgres pool | 50 pooled Postgres connections |
