# StreamPulse Architecture

## Current Status

**Phase:** 0 – Project Initialization

The repository structure has been created, but no services have been started yet.

---

## Implemented

- Git repository
- Project folder structure
- Environment template (`.env.example`)
- Docker Compose configuration for Redpanda
- Documentation structure

---

## Planned Next Step

Phase 1 will introduce:

```
Python Producer
        │
        ▼
   Redpanda Topic
```

At the end of Phase 1, the producer will publish synthetic order events into the `orders` topic.

---

## Current Architecture

```text
Repository
│
├── Documentation
├── Configuration
├── Docker Compose
└── Placeholder Application Code
```

No containers or services are currently running.
