# Instrumentation Demo

This example demonstrates Mitsuki's instrumentation and metrics capabilities with Grafana visualization:

- **Auto-instrumentation**: Single `@Instrumented` decorator on `@Application` instruments all components
- **System metrics**: CPU, memory, uptime tracking
- **HTTP metrics**: Request counts, latency percentiles, per-endpoint statistics
- **Component metrics**: Service/repository method timing, error rates
- **Custom operational metrics**: Database operations, query performance, resource usage
- **Grafana dashboards**: Pre-configured for visualization
- **Prometheus format**: Compatible with Prometheus/Grafana scraping

## Quick Start

### 1. Start the services

```bash
docker-compose up -d
```

This will start the Mitsuki application, Prometheus, and Grafana.

- **Mitsuki**: `http://localhost:8000`
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3000` (username: `admin`, password: `admin`)

### 2. Generate some traffic
```bash
# Create users
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com"}'

curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "email": "bob@example.com"}'

# Get users (triggers database query metrics)
curl http://localhost:8000/api/users

# Create orders (tracks database writes)
curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "product_type": "digital", "amount": 99.99, "region": "us-east"}'

curl -X POST http://localhost:8000/api/orders \
  -H "Content-Type: application/json" \
  -d '{"user_id": 2, "product_type": "physical", "amount": 49.99, "region": "eu-west"}'

# Get all orders (triggers full table scan metric)
curl http://localhost:8000/api/orders

# Get user orders (tracks query row count)
curl http://localhost:8000/api/orders/user/1

# Calculate revenue (expensive aggregation metric)
curl http://localhost:8000/api/orders/revenue
```

### 3. View metrics

**Grafana Dashboard:**
Open `http://localhost:3000` and navigate to "Mitsuki Application Metrics" dashboard.

**Prometheus UI:**
Open `http://localhost:9090` to access the Prometheus UI. You can use the expression browser to query metrics.

**Raw metrics endpoints:**
```bash
# Mitsuki format (human-readable JSON)
curl http://localhost:8000/metrics

# Prometheus format (for Grafana/Prometheus scraping)
curl http://localhost:8000/metrics/prometheus
```

## What Gets Tracked

### Automatic Metrics

All services, repositories, and controllers are automatically instrumented:

- **HTTP requests**: Status codes, latency percentiles (p50, p95, p99), per-endpoint stats
- **Component calls**: Count, error rate, execution time (min/max/avg)
- **System resources**: CPU usage, memory (RSS, VMS)

### Custom Operational Metrics

The `OrderService` demonstrates tracking operational metrics:

1. **Database Write Operations** (`database_writes_total`)
   - Tracks all INSERT/UPDATE/DELETE operations
   - Labels: `table`, `operation`

2. **Query Result Sizes** (`database_query_rows_returned`)
   - Tracks how many rows each query returns
   - Labels: `table`, `query_type`

3. **Full Table Scans** (`database_full_scan_total`)
   - Counts expensive table scan operations
   - Labels: `table`

4. **Expensive Aggregations** (`expensive_aggregation_total`)
   - Tracks resource-intensive calculations
   - Labels: `operation`, `records_processed`

## Dashboard Panels

The configured Grafana dashboard includes:

### Overview Statistics
1. **Total Requests**: Counter of all HTTP requests
2. **Requests/Second**: Real-time request rate
3. **Avg Response Time**: Average latency across all endpoints
4. **Error Rate**: Percentage of failed requests
5. **P95 Latency**: 95th percentile response time
6. **P99 Latency**: 99th percentile response time

### HTTP Performance - Per Route Breakdown
7. **Response Time by Route**: Latency breakdown per endpoint
8. **Request Rate by Route**: Traffic distribution
9. **Response Time Percentiles**: p50/p95/p99 over time
10. **Status Code Distribution**: Success vs error responses

### Component Performance
11. **Component Metrics**: Call counts and durations
12. **Component Call Rate**: Service/repository call frequency
13. **Component Duration (P95)**: 95th percentile duration by component
14. **Component Success vs Failure**: Error tracking per component

### Database & Operations
15. **Database Write Operations**: Write load by table and operation
16. **Query Result Sizes**: Rows returned per query (detect large queries)
17. **Full Table Scans**: Expensive scan operations (should be LOW!)
18. **Expensive Aggregations**: Resource-intensive operations

### System Resources
19. **Memory Usage**: RSS and VMS memory tracking
20. **CPU Usage**: Process CPU percentage

## Configuration

The example uses the following configuration in `application.yml`:

```yaml
instrumentation:
  enabled: true        # Enable instrumentation
  track_memory: true   # Track memory with tracemalloc

metrics:
  enabled: true
  path: /metrics
  # Allow access from:
  # - Docker internal network range (172.16.0.0/12) - i.e. 172.16.0.0 to 172.31.255.255
  # - Local network range (192.168.0.0/16)
  allowed_ips: ["172.16.0.0/12", "192.168.0.0/16"]  # Empty list = allow all. For production, specify your network ranges.
```

## Metrics Endpoints

### /metrics 

Nested JSON with computed aggregations, nice for human readability, direct API consumption (i.e. custom dashboards) or debugging.

Example response:
```json
{
  "enabled": true,
  "timestamp": "2025-12-15T10:30:00.000000",
  "instrumentation": {
    "system": {
      "memory": {"rss_mb": 85.2, "vms_mb": 150.3},
      "cpu": {"percent": 1.2}
    },
    "http": {
      "total_requests": 15,
      "requests_by_method": {"GET": 10, "POST": 5},
      "latency": {"avg_ms": 8.5, "p95_ms": 35.1}
    },
    "components": {
      "UserService": {"calls": 12, "avg_duration_ms": 5.2},
      "OrderService": {"calls": 8, "avg_duration_ms": 12.1}
    }
  }
}
```

### /metrics/prometheus (Prometheus Format)

Flat text format with labels, good for Prometheus scraping/Grafana integration, time series analysis, etc.

Example response:
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/users",status="200"} 10.0

# HELP database_writes_total Database write operations
# TYPE database_writes_total counter
database_writes_total{table="orders",operation="insert"} 5.0
```

## Code Organization

```
instrumentation_demo/
├── app.py                          # Application entry point with @Instrumented
├── application.yml                 # Configuration
├── docker-compose.yml              # Docker setup for Prometheus + Grafana
├── prometheus.yml                  # Prometheus scraping config
├── grafana/
│   └── dashboards/
│       └── mitsuki-metrics.json    # Pre-built dashboard
└── src/
    ├── controllers/
    │   ├── user_controller.py      # REST endpoints for users
    │   └── order_controller.py     # REST endpoints for orders
    ├── services/
    │   ├── user_service.py         # Business logic
    │   └── order_service.py        
    ├── repositories/
    │   ├── user_repository.py      # Data access, auto-instrumented
    │   └── order_repository.py     # In-memory storage
    └── domain/
        ├── user.py                 # User entity
        └── order.py                # Order entity
```

## Custom Metrics Example

The `OrderService` shows how to track operational metrics:

```python
from mitsuki.core.instrumentation import InstrumentationProvider

@Service()
class OrderService:
    def __init__(self, order_repo: OrderRepository, instrumentation: InstrumentationProvider):
        self.order_repo = order_repo
        self.instrumentation = instrumentation

    async def create_order(self, user_id: int, product_type: str, amount: float, region: str):
        order = Order(user_id=user_id, product_type=product_type, amount=amount, region=region)
        saved_order = await self.order_repo.save(order)

        # Track database write operation
        self.instrumentation.record_metric(
            metric_name="database_writes_total",
            value=1,
            labels={"table": "orders", "operation": "insert"}
        )

        return saved_order
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Mitsuki Application             │
│  ┌───────────────────────────────────┐  │
│  │  @Instrumented Components         │  │
│  │  - UserService                    │  │
│  │  - OrderService                   │  │
│  │  - UserRepository                 │  │
│  │  - OrderRepository                │  │
│  │  - Controllers                    │  │
│  └───────────────────────────────────┘  │
│                 ↓                       │
│  ┌───────────────────────────────────┐  │
│  │  Instrumentation Middleware       │  │
│  │  - HTTP request tracking          │  │
│  │  - Component call tracking        │  │
│  │  - System metrics collection      │  │
│  └───────────────────────────────────┘  │
│                 ↓                       │
│  ┌───────────────────────────────────┐  │
│  │  Metrics Storage                  │  │
│  │  - Counters (requests, calls)     │  │
│  │  - Gauges (memory, CPU)           │  │
│  │  - Histograms (latency, duration) │  │
│  └───────────────────────────────────┘  │
│                 ↓                       │
│  ┌───────────────────────────────────┐  │
│  │  /metrics Endpoint                │  │
│  │  - Format selection               │  │
│  │  - IP allowlisting                │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│            Prometheus                   │
│  - Scrapes /metrics/prometheus          │
│  - Stores time-series data              │
└─────────────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────┐
│              Grafana                    │
│  - Queries Prometheus                   │
│  - Renders dashboards                   │
└─────────────────────────────────────────┘
```

## Cleanup

```bash
# Stop all services
docker-compose down

# Remove volumes
docker-compose down -v
```

