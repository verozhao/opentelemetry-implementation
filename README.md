# OpenTelemetry Implementation with FastAPI & OpenSearch

A distributed tracing implementation showcasing OpenTelemetry with FastAPI microservices, OpenSearch for trace storage, and comprehensive observability features.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Service  │───▶│ Product Service │    │ OpenTelemetry   │
│   (Port 8001)   │    │   (Port 8002)   │───▶│   Collector     │
│                 │    │                 │    │   (Port 4317)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    OpenSearch   │    │     Jaeger      │    │   OpenSearch    │
│   (Port 9200)   │    │  (Port 16686)   │    │   Dashboards    │
│                 │    │                 │    │   (Port 5601)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Features

- **Distributed Tracing**: Complete request tracing across microservices
- **OpenTelemetry Integration**: Industry-standard observability framework
- **OpenSearch Storage**: Scalable trace and log storage with dashboards
- **Jaeger UI**: Intuitive trace visualization and analysis
- **Structured Logging**: JSON-formatted logs with trace correlation
- **Health Checks**: Service health monitoring endpoints
- **Metrics Collection**: Application and business metrics
- **Error Handling**: Comprehensive error tracking and propagation
- **Context Propagation**: Seamless trace context across service boundaries

## Quick Start

### Prerequisites

- Docker & Docker Compose
- `curl` and `jq` (for testing)
- Make (optional, for convenience commands)

### 1. Clone and Setup

```bash
git clone https://github.com/verozhao/opentelemetry-implementation
cd opentelemetry-implementation
cp .env.example .env
```

### 2. Start All Services

```bash
# Using Docker Compose
docker-compose up -d

# Or using Make
make up
```

### 3. Verify Services

```bash
# Check service health
make health

# Or manually
curl http://localhost:8001/health
curl http://localhost:8002/health
```

### 4. Generate Traces

```bash
# Test the full distributed trace flow
make test-flow

# Or manually test cross-service communication
curl http://localhost:8001/users/1/recommendations
```

### 5. View Traces

- **Jaeger UI**: http://localhost:16686
- **OpenSearch Dashboards**: http://localhost:5601

## API Documentation

### User Service (Port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/users` | GET | List all users |
| `/users/{id}` | GET | Get user by ID |
| `/users` | POST | Create new user |
| `/users/{id}/recommendations` | GET | Get personalized recommendations |
| `/metrics` | GET | Service metrics |

### Product Service (Port 8002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/products` | GET | List products with filters |
| `/products/{id}` | GET | Get product by ID |
| `/products` | POST | Create new product |
| `/products/recommend` | GET | Get product recommendations |
| `/products/category/{name}` | GET | Get products by category |
| `/categories` | GET | List all categories |
| `/metrics` | GET | Service metrics |

### Example API Calls

```bash
# Create a user
curl -X POST http://localhost:8001/users \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice Johnson", "email": "alice@example.com", "preferences": {"category": "electronics"}}'

# Get recommendations (triggers cross-service call)
curl http://localhost:8001/users/1/recommendations?limit=3

# Get products by category
curl http://localhost:8002/products/category/electronics

# Create a product
curl -X POST http://localhost:8002/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Gaming Mouse", "category": "electronics", "price": 79.99, "description": "High-precision gaming mouse", "inventory": 25}'
```

## Development

### Local Development Setup

```bash
# Start only infrastructure services
make dev-setup

# Run services locally for development
cd services/user-service && python main.py &
cd services/product-service && python main.py &
```

### Available Make Commands

```bash
make build          # Build all Docker images
make up             # Start all services
make down           # Stop all services
make logs           # View logs from all services
make clean          # Clean up all containers and volumes
make health         # Check service health
make test-flow      # Test the complete request flow
make metrics        # View service metrics
make jaeger         # Open Jaeger UI
make opensearch     # Open OpenSearch Dashboards
```

### Environment Variables

Key configuration options in `.env`:

```bash
# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_RESOURCE_ATTRIBUTES=service.name=my-service,service.version=1.0.0

# Services
SERVICE_NAME=user-service
PRODUCT_SERVICE_URL=http://product-service:8000

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Observability Features

### Distributed Tracing

- **Automatic Instrumentation**: FastAPI, HTTP client, and logging instrumentation
- **Manual Spans**: Custom business logic tracing
- **Span Events**: Key operation markers
- **Span Attributes**: Rich metadata for filtering and analysis
- **Error Recording**: Automatic exception capture

### Logging

- **Structured Logging**: JSON format with trace correlation
- **Log Levels**: Configurable log levels per service
- **Trace Context**: Automatic trace ID injection in logs

### Metrics

- **Service Metrics**: Health, performance, and business metrics
- **OpenTelemetry Metrics**: Automatic metric collection
- **Custom Metrics**: Business-specific measurements

## Production Considerations

### Security

- **No Security Plugins Disabled**: OpenSearch security disabled for demo
- **Container Security**: Run with non-root users
- **Network Security**: Use proper network policies
- **Secrets Management**: Use proper secret management solutions

### Scaling

- **Horizontal Scaling**: Services are stateless and scalable
- **Load Balancing**: Add load balancers for production
- **Resource Limits**: Configure appropriate CPU/memory limits
- **OpenSearch Cluster**: Scale OpenSearch for production workloads

### Monitoring

- **Health Checks**: Kubernetes readiness/liveness probes
- **Alerting**: Set up alerts on key metrics
- **SLIs/SLOs**: Define service level indicators and objectives

## Troubleshooting

### Common Issues

1. **Services not starting**
   ```bash
   # Check logs
   docker-compose logs -f
   
   # Ensure ports are not in use
   netstat -tlnp | grep -E '(8001|8002|9200|16686)'
   ```

2. **No traces appearing**
   ```bash
   # Check OpenTelemetry collector
   docker-compose logs otel-collector
   
   # Verify service configuration
   curl http://localhost:8001/health
   ```

3. **OpenSearch not starting**
   ```bash
   # Check system resources
   docker stats
   
   # Increase Docker memory limit if needed
   # macOS: Docker Desktop > Resources > Memory > 4GB+
   ```

### Debug Commands

```bash
# View all container statuses
docker-compose ps

# Follow logs for specific service
docker-compose logs -f user-service

# Execute commands in containers
docker-compose exec user-service /bin/bash

# Reset everything
make clean && make up
```

## Technologies Used

- **FastAPI**: Modern Python web framework
- **OpenTelemetry**: Observability framework
- **OpenSearch**: Search and analytics engine
- **Jaeger**: Distributed tracing platform
- **Docker**: Containerization
- **HTTPX**: Async HTTP client
- **Structlog**: Structured logging
- **Pydantic**: Data validation

## License

This project is licensed under the MIT License - see the LICENSE file for details.