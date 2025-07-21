.PHONY: build up down logs clean test health

# Build all services
build:
	docker-compose build

# Start all services
up:
	docker-compose up -d

# Stop all services
down:
	docker-compose down

# View logs from all services
logs:
	docker-compose logs -f

# Clean up everything (containers, images, volumes)
clean:
	docker-compose down -v --rmi all --remove-orphans

# Run basic health checks
health:
	@echo "Checking service health..."
	@curl -s http://localhost:8001/health | jq .
	@curl -s http://localhost:8002/health | jq .
	@echo "OpenSearch status:"
	@curl -s http://localhost:9200/_cluster/health | jq .

# Test the full flow
test-flow:
	@echo "Testing user service..."
	@curl -s http://localhost:8001/users | jq .
	@echo "\nTesting product service..."
	@curl -s http://localhost:8002/products | jq .
	@echo "\nTesting user recommendations (cross-service call)..."
	@curl -s http://localhost:8001/users/1/recommendations | jq .

# View Jaeger UI
jaeger:
	@echo "Opening Jaeger UI at http://localhost:16686"
	@open http://localhost:16686 2>/dev/null || echo "Open http://localhost:16686 in your browser"

# View OpenSearch Dashboards
opensearch:
	@echo "Opening OpenSearch Dashboards at http://localhost:5601"
	@open http://localhost:5601 2>/dev/null || echo "Open http://localhost:5601 in your browser"

# Development setup
dev-setup:
	cp .env.example .env
	docker-compose up -d opensearch opensearch-dashboards jaeger otel-collector
	@echo "Development infrastructure started. Run 'make up' to start all services."

# View metrics
metrics:
	@echo "User service metrics:"
	@curl -s http://localhost:8001/metrics | jq .
	@echo "\nProduct service metrics:"
	@curl -s http://localhost:8002/metrics | jq .