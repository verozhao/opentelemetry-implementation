# OpenTelemetry Distributed Tracing Demo

Simple demo showing distributed tracing between two FastAPI services using OpenTelemetry.

## What This Does

- User Service calls Product Service
- OpenTelemetry traces the request across both services
- View traces in Jaeger UI

## Setup & Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Infrastructure (Jaeger + OpenTelemetry Collector)
```bash
docker-compose up -d
```

### 3. Start Services

**Terminal 1 - Product Service:**
```bash
cd services/product-service
python main.py
```
This starts on `http://localhost:8000`

**Terminal 2 - User Service:**
```bash
cd services/user-service
PRODUCT_SERVICE_URL=http://localhost:8000 python main.py
```
This starts on `http://localhost:8000` (will conflict - need to change port)

**Fix port conflict - Edit user service main.py:**
Change the last line to:
```python
uvicorn.run(app, host="0.0.0.0", port=8001)
```

**Restart User Service:**
```bash
cd services/user-service
PRODUCT_SERVICE_URL=http://localhost:8000 python main.py
```
Now runs on `http://localhost:8001`

## Test Distributed Tracing

### 1. Test Individual Services
```bash
# Product service
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"product-service"}

# User service  
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"user-service"}
```

### 2. Test Cross-Service Call (Creates Distributed Trace)
```bash
curl http://localhost:8001/users/1/recommendations
```

**Expected Response:**
```json
{
  "user": {
    "id": 1,
    "name": "John Doe", 
    "email": "john@example.com"
  },
  "products": [
    {"id": 1, "name": "Laptop Pro", "category": "electronics", "price": 1299.99},
    {"id": 2, "name": "Wireless Headphones", "category": "electronics", "price": 199.99},
    {"id": 3, "name": "Programming Book", "category": "books", "price": 49.99}
  ]
}
```

### 3. View Traces in Jaeger
1. Open http://localhost:16686
2. Select "user-service" from the Service dropdown
3. Click "Find Traces"
4. Click on a trace to see the distributed request flow:
   - `user-service: get_user_recommendations` 
   - `product-service: recommend_products`

## Troubleshooting

**Services won't start:**
- Check ports aren't in use: `lsof -i :8000` and `lsof -i :8001`
- Make sure you edited user service to use port 8001

**No traces in Jaeger:**
- Wait 10-20 seconds after making requests
- Check services are running: `curl http://localhost:8000/health`
- Check docker containers: `docker-compose ps`

**Port conflicts:**
- Product service: port 8000
- User service: port 8001 (after editing)
- Jaeger UI: port 16686

## Stop Everything
```bash
# Stop Python services: Ctrl+C in terminals
# Stop infrastructure:
docker-compose down
```

## Files Explained
- `services/user-service/main.py` - User service (calls Product service)
- `services/product-service/main.py` - Product service (returns recommendations)
- `docker-compose.yml` - Runs Jaeger, OpenTelemetry Collector, OpenSearch
- `otel-collector-config.yaml` - Routes traces from services to Jaeger