import os
import logging
import asyncio
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from opentelemetry import trace, baggage, context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.propagate import inject, extract
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.semconv.trace import SpanAttributes

import structlog

SERVICE_NAME = os.getenv("SERVICE_NAME", "user-service")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8002")

resource = Resource.create({
    "service.name": SERVICE_NAME,
    "service.version": "1.0.0",
    "service.instance.id": f"{SERVICE_NAME}-1",
})

trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(
    endpoint=OTEL_ENDPOINT,
    insecure=True,
)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting user service", service=SERVICE_NAME)
    yield
    logger.info("Shutting down user service", service=SERVICE_NAME)

app = FastAPI(
    title="User Service",
    description="Handles user operations and calls product service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
LoggingInstrumentor().instrument(set_logging_format=True)

class User(BaseModel):
    id: int = Field(..., description="User ID")
    name: str = Field(..., description="User name")
    email: str = Field(..., description="User email")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")

class UserCreate(BaseModel):
    name: str = Field(..., description="User name")
    email: str = Field(..., description="User email")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")

class UserRecommendation(BaseModel):
    user: User
    recommended_products: list
    recommendation_score: float

users_db: Dict[int, User] = {
    1: User(id=1, name="John Doe", email="john@example.com", preferences={"category": "electronics"}),
    2: User(id=2, name="Jane Smith", email="jane@example.com", preferences={"category": "books"}),
}

async def get_http_client():
    return httpx.AsyncClient(timeout=30.0)

@app.get("/health")
async def health_check():
    with tracer.start_as_current_span("health_check") as span:
        span.set_attribute("service.name", SERVICE_NAME)
        span.set_attribute("health.status", "healthy")
        logger.info("Health check requested")
        return {"status": "healthy", "service": SERVICE_NAME}

@app.get("/users", response_model=list[User])
async def get_users(request: Request):
    with tracer.start_as_current_span("get_users") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("users.count", len(users_db))
        
        logger.info("Fetching all users", user_count=len(users_db))
        
        span.add_event("users_retrieved", {"count": len(users_db)})
        span.set_status(Status(StatusCode.OK))
        
        return list(users_db.values())

@app.get("/users/{user_id}", response_model=User)
async def get_user(user_id: int, request: Request):
    with tracer.start_as_current_span("get_user") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("user.id", user_id)
        
        logger.info("Fetching user", user_id=user_id)
        
        if user_id not in users_db:
            span.record_exception(HTTPException(status_code=404, detail="User not found"))
            span.set_status(Status(StatusCode.ERROR, "User not found"))
            logger.warning("User not found", user_id=user_id)
            raise HTTPException(status_code=404, detail="User not found")
        
        user = users_db[user_id]
        span.add_event("user_found", {"user.name": user.name, "user.email": user.email})
        span.set_status(Status(StatusCode.OK))
        
        return user

@app.post("/users", response_model=User, status_code=201)
async def create_user(user_data: UserCreate, request: Request):
    with tracer.start_as_current_span("create_user") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "POST")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("user.name", user_data.name)
        span.set_attribute("user.email", user_data.email)
        
        logger.info("Creating new user", user_name=user_data.name, user_email=user_data.email)
        
        new_id = max(users_db.keys()) + 1 if users_db else 1
        new_user = User(id=new_id, **user_data.dict())
        users_db[new_id] = new_user
        
        span.add_event("user_created", {"user.id": new_id, "user.name": new_user.name})
        span.set_status(Status(StatusCode.OK))
        
        logger.info("User created successfully", user_id=new_id, user_name=new_user.name)
        
        return new_user

@app.get("/users/{user_id}/recommendations", response_model=UserRecommendation)
async def get_user_recommendations(
    user_id: int, 
    request: Request,
    limit: int = 5,
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    with tracer.start_as_current_span("get_user_recommendations") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("user.id", user_id)
        span.set_attribute("recommendation.limit", limit)
        
        logger.info("Getting user recommendations", user_id=user_id, limit=limit)
        
        if user_id not in users_db:
            span.record_exception(HTTPException(status_code=404, detail="User not found"))
            span.set_status(Status(StatusCode.ERROR, "User not found"))
            logger.warning("User not found for recommendations", user_id=user_id)
            raise HTTPException(status_code=404, detail="User not found")
        
        user = users_db[user_id]
        
        with tracer.start_as_current_span("call_product_service") as product_span:
            product_span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
            product_span.set_attribute("service.name", "product-service")
            product_span.set_attribute("user.preferences", str(user.preferences))
            
            headers = {}
            inject(headers)
            
            try:
                logger.info("Calling product service for recommendations", 
                           user_id=user_id, 
                           product_service_url=PRODUCT_SERVICE_URL)
                
                response = await http_client.get(
                    f"{PRODUCT_SERVICE_URL}/products/recommend",
                    params={
                        "category": user.preferences.get("category", "general"),
                        "limit": limit
                    },
                    headers=headers
                )
                response.raise_for_status()
                products = response.json()
                
                product_span.set_attribute("products.count", len(products))
                product_span.add_event("products_received", {"count": len(products)})
                product_span.set_status(Status(StatusCode.OK))
                
                logger.info("Received product recommendations", 
                           user_id=user_id, 
                           product_count=len(products))
                
            except httpx.RequestError as e:
                product_span.record_exception(e)
                product_span.set_status(Status(StatusCode.ERROR, str(e)))
                logger.error("Failed to call product service", 
                            error=str(e), 
                            user_id=user_id)
                raise HTTPException(status_code=503, detail="Product service unavailable")
            
            except httpx.HTTPStatusError as e:
                product_span.record_exception(e)
                product_span.set_status(Status(StatusCode.ERROR, f"HTTP {e.response.status_code}"))
                logger.error("Product service returned error", 
                            status_code=e.response.status_code, 
                            user_id=user_id)
                raise HTTPException(status_code=e.response.status_code, detail="Product service error")
        
        recommendation_score = min(0.95, 0.7 + (len(products) * 0.05))
        
        recommendation = UserRecommendation(
            user=user,
            recommended_products=products,
            recommendation_score=recommendation_score
        )
        
        span.add_event("recommendations_generated", {
            "user.id": user_id,
            "products.count": len(products),
            "recommendation.score": recommendation_score
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info("User recommendations generated successfully", 
                   user_id=user_id, 
                   product_count=len(products),
                   score=recommendation_score)
        
        return recommendation

@app.get("/metrics")
async def get_metrics():
    with tracer.start_as_current_span("get_metrics") as span:
        span.set_attribute("metrics.type", "application")
        
        metrics = {
            "service": SERVICE_NAME,
            "users_count": len(users_db),
            "uptime": "running",
            "version": "1.0.0"
        }
        
        span.add_event("metrics_collected", metrics)
        logger.info("Metrics collected", **metrics)
        
        return metrics

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)