# StateFlow

**A Distributed Transaction and Process Management Platform**

StateFlow is a production-ready platform for building reliable, scalable distributed transactions using the **Saga pattern**. It provides workflow orchestration, saga-based compensation, outbox pattern for event publishing, and comprehensive observability.

---

## 🎯 What It Does

StateFlow solves the challenge of managing **distributed transactions across microservices** by providing:

| Problem | Solution |
|---------|----------|
| Coordinating multi-step operations across services | **Saga Orchestrator** - defines workflows as sequences of steps with compensating actions |
| Handling partial failures gracefully | **Automatic Compensation** - rolls back completed steps when any step fails |
| Reliable event publishing | **Transactional Outbox** - guarantees events are published exactly once |
| Horizontal scaling & fault tolerance | **Celery Workers + RabbitMQ** - distributed task execution with retries |
| Visibility into production systems | **OpenTelemetry + Prometheus + Grafana** - full observability stack |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js 14)                       │
│                    React + TypeScript + TanStack Query              │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ REST API (JWT Auth)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Backend API (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │  Workflows  │  │ Executions  │  │  Workers    │  │ Auth/Org  │  │
│  │   CRUD      │  │  Management │  │  Registry   │  │  Management│ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
│           │               │               │               │        │
│           ▼               ▼               ▼               ▼        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Saga Execution Engine                           │   │
│  │  • Step execution with retries                               │   │
│  │  • Compensation on failure                                   │   │
│  │  • Idempotency guarantees                                    │   │
│  │  • Async/await with SQLAlchemy + asyncpg                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│   PostgreSQL     │  │    RabbitMQ      │  │     Redis        │
│  (Primary DB)    │  │  (Message Broker)│  │  (Cache/Celery)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Observability Stack                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │ Prometheus  │  │   Grafana   │  │ OpenTelemetry│  │ AlertMgr  │  │
│  │  (Metrics)  │  │ (Dashboards)│  │  (Tracing)   │  │ (Alerts)  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Key Features

### Workflow Engine
- **Visual workflow designer** (JSON-based definitions)
- **Versioned workflows** - iterate safely
- **Step types**: HTTP calls, database operations, custom code, delays, parallel execution
- **Conditional branching** and loops

### Saga Pattern Implementation
- **Forward execution** with automatic retries (configurable backoff)
- **Backward compensation** - automatic rollback on failure
- **Timeout handling** - saga-level and step-level timeouts
- **Idempotency keys** - safe retries without duplicate effects

### Outbox Pattern
- **Transactional outbox** - events written atomically with business data
- **Background publisher** - reliable event delivery to message broker
- **At-least-once delivery** with deduplication support

### Worker Management
- **Dynamic worker registration** with heartbeats
- **Capacity-based scheduling** - route tasks to appropriate workers
- **Graceful shutdown** - drain in-flight tasks

### Observability (Phase 8)
- **Distributed tracing** via OpenTelemetry (FastAPI, SQLAlchemy, Redis, Celery)
- **Metrics**: Request latency, error rates, queue depths, worker health
- **Pre-built Grafana dashboards**: System Overview, Workflow Executions, Workers
- **Alert rules**: 7 groups, 20+ rules (backend, DB, workers, Redis, RabbitMQ, system, workflows)

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop
- Node.js 18+ (for frontend development)
- Python 3.12+ (for backend development)

### Using Docker Compose (Recommended)

```bash
# Clone and navigate
cd Stateflow

# Start all services
docker-compose up -d

# Wait for services to be healthy (~30 seconds)
# Check status
docker-compose ps
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | Register new account |
| **Grafana** | http://localhost:3000 | admin / admin |
| **API Docs** | http://localhost:8000/docs | - |
| **Prometheus** | http://localhost:9090 | - |
| **RabbitMQ** | http://localhost:15672 | stateflow / stateflow_dev_password |

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Configure as needed
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev

# Workers (separate terminal)
cd backend
celery -A app.workers.tasks.celery_app worker --loglevel=INFO
celery -A app.workers.tasks.celery_app beat --loglevel=INFO
```

---

## 📖 Core Concepts

### Workflow Definition
```json
{
  "name": "Order Processing",
  "version": "1.0.0",
  "steps": [
    {
      "name": "reserve_inventory",
      "type": "http",
      "config": {
        "url": "http://inventory-service/reserve",
        "method": "POST"
      },
      "compensation": {
        "type": "http",
        "config": {
          "url": "http://inventory-service/release",
          "method": "POST"
        }
      },
      "retry_policy": {
        "max_attempts": 3,
        "backoff_seconds": 2
      }
    },
    {
      "name": "process_payment",
      "type": "http",
      "config": {
        "url": "http://payment-service/charge",
        "method": "POST"
      },
      "compensation": {
        "type": "http",
        "config": {
          "url": "http://payment-service/refund",
          "method": "POST"
        }
      }
    }
  ]
}
```

### Creating a Workflow Execution
```bash
curl -X POST http://localhost:8000/api/v1/executions \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "wf_123",
    "input_data": {"order_id": "ord_456", "amount": 99.99}
  }'
```

---

## 🔧 Configuration

Key environment variables (`.env` or docker-compose.yml):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection | `redis://redis:6379/0` |
| `RABBITMQ_URL` | RabbitMQ connection | `amqp://stateflow:...` |
| `SECRET_KEY` | JWT signing key | **Change in production!** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT access token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | JWT refresh token TTL | `7` |
| `OTLP_ENDPOINT` | OpenTelemetry collector | `http://prometheus:4317` |
| `TRACING_ENABLED` | Enable OpenTelemetry | `true` |

---

## 📊 Observability

### Grafana Dashboards (Auto-provisioned)
1. **StateFlow / System Overview** - Infrastructure health (CPU, memory, disk, network)
2. **StateFlow / Workflow Executions** - Execution rates, latency, success/failure, compensation triggers
3. **StateFlow / Workers** - Worker count, task throughput, queue depths, heartbeats

### Prometheus Alerts
- **Backend**: Down, high latency, high error rate, memory
- **Database**: Down, connection pool exhaustion, slow queries
- **Workers**: Down, queue backlog, task failures, memory
- **Redis**: Down, memory pressure, client connections
- **RabbitMQ**: Down, queue backlog, no consumers
- **System**: CPU, memory, disk, load
- **Workflows**: Execution failures, queue backlog, compensations, retries, saga timeouts

### Distributed Tracing
OpenTelemetry spans automatically generated for:
- HTTP requests (FastAPI middleware)
- Database queries (SQLAlchemy)
- Redis operations
- Celery tasks

---

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest -v

# Frontend tests
cd frontend
npm test

# Integration tests (requires running services)
cd backend
pytest tests/integration -v
```

---

## 📁 Project Structure

```
Stateflow/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # REST endpoints
│   │   ├── core/             # Config, DB, logging, telemetry
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── workers/          # Celery tasks & scheduler
│   │   └── main.py           # FastAPI app factory
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic/              # DB migrations
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages
│   │   ├── components/       # React components
│   │   ├── lib/              # Stores, utilities
│   │   ├── services/         # API client
│   │   └── types/            # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── monitoring/
│   ├── prometheus.yml        # Prometheus config
│   ├── prometheus/rules/     # Alert rules
│   └── grafana/provisioning/ # Dashboards & datasources
└── docker-compose.yml
```

---

## 🔐 Security

- **JWT authentication** with access/refresh token rotation
- **Password hashing** with bcrypt
- **CORS** configured for frontend origin
- **SQL injection protection** via SQLAlchemy ORM
- **Rate limiting** (configurable)

---

## 📦 Production Deployment

1. **Update secrets** in `.env` or Docker secrets
2. **Use managed services**: RDS, ElastiCache, CloudAMQP
3. **Enable TLS** on all connections
4. **Configure Alertmanager** for notification routing
5. **Set up log aggregation** (Loki, ELK, or CloudWatch)
6. **Run multiple worker replicas** for HA

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a PR

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- **FastAPI** - Modern, fast web framework
- **Next.js** - React framework for production
- **Celery** - Distributed task queue
- **OpenTelemetry** - Observability framework
- **Prometheus/Grafana** - Monitoring stack