# OpenTelemetry Implementation with FastAPI

A simple distributed tracing implementation showcasing OpenTelemetry with two FastAPI microservices.

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
- **Simple Setup**: Minimal configuration for learning and testing
- **Cross-Service Communication**: User service calls Product service with trace propagation

## Quick Start

### Prerequisites

- Python 3.8+
- Docker & Docker Compose
- `pip install fastapi httpx opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-httpx opentelemetry-exporter-otlp`

### 1. Start Infrastructure

```bash
# Start OpenTelemetry Collector, Jaeger, and OpenSearch
docker-compose up -d

# Verify services are running
curl http://localhost:9200/_cluster/health
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Services

```bash
# Terminal 1 - User Service (port 8001)
cd services/user-service
SERVICE_NAME=user-service PRODUCT_SERVICE_URL=http://localhost:8002 python main.py

# Terminal 2 - Product Service (port 8002)  
cd services/product-service
SERVICE_NAME=product-service python main.py
```

### 4. Test Distributed Tracing

```bash
# Test individual services
curl http://localhost:8001/health
curl http://localhost:8002/health

# Test cross-service call (creates distributed trace)
curl http://localhost:8001/users/1/recommendations
```

### 5. View Traces

- **Jaeger UI**: http://localhost:16686
- **OpenSearch Dashboards**: http://localhost:5601

## API Endpoints

### User Service (Port 8001)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /users` | List all users |
| `GET /users/{id}` | Get user by ID |
| `GET /users/{id}/recommendations` | Get recommendations (calls Product Service) |

### Product Service (Port 8002)

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /products` | List all products |
| `GET /products/recommend` | Get product recommendations |

## Testing Distributed Tracing

The key endpoint for testing distributed tracing is:

```bash
curl http://localhost:8001/users/1/recommendations
```

This creates a trace that spans both services:
1. User Service receives request
2. User Service calls Product Service `/products/recommend`
3. Product Service returns recommendations
4. User Service returns combined response

View the complete trace in Jaeger UI to see the distributed request flow.

## Environment Variables

- `SERVICE_NAME`: Service identifier for OpenTelemetry
- `OTEL_EXPORTER_OTLP_ENDPOINT`: OpenTelemetry Collector endpoint (default: http://localhost:4317)
- `PRODUCT_SERVICE_URL`: Product service URL for user service calls

## Stopping Services

```bash
# Stop infrastructure
docker-compose down

# Stop Python services with Ctrl+C
```

## Technologies Used

- **FastAPI**: Python web framework
- **OpenTelemetry**: Observability framework
- **OpenSearch**: Search and analytics engine
- **Jaeger**: Distributed tracing platform
- **Docker**: Infrastructure containerization
- **HTTPX**: Async HTTP client

## License

MIT License