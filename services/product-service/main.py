import os
import logging
import asyncio
import random
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from opentelemetry import trace, baggage, context
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.propagate import extract
from opentelemetry.trace.status import Status, StatusCode
from opentelemetry.semconv.trace import SpanAttributes

import structlog

SERVICE_NAME = os.getenv("SERVICE_NAME", "product-service")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

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
    logger.info("Starting product service", service=SERVICE_NAME)
    yield
    logger.info("Shutting down product service", service=SERVICE_NAME)

app = FastAPI(
    title="Product Service",
    description="Handles product operations and recommendations",
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
LoggingInstrumentor().instrument(set_logging_format=True)

class Product(BaseModel):
    id: int = Field(..., description="Product ID")
    name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    price: float = Field(..., description="Product price")
    rating: float = Field(..., description="Product rating")
    description: str = Field(..., description="Product description")
    inventory: int = Field(..., description="Available inventory")

class ProductCreate(BaseModel):
    name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    price: float = Field(..., description="Product price")
    description: str = Field(..., description="Product description")
    inventory: int = Field(default=0, description="Available inventory")

products_db: Dict[int, Product] = {
    1: Product(
        id=1, 
        name="Laptop Pro", 
        category="electronics", 
        price=1299.99, 
        rating=4.5,
        description="High-performance laptop for professionals", 
        inventory=50
    ),
    2: Product(
        id=2, 
        name="Wireless Headphones", 
        category="electronics", 
        price=199.99, 
        rating=4.3,
        description="Premium noise-cancelling headphones", 
        inventory=25
    ),
    3: Product(
        id=3, 
        name="Programming Fundamentals", 
        category="books", 
        price=49.99, 
        rating=4.7,
        description="Complete guide to programming concepts", 
        inventory=100
    ),
    4: Product(
        id=4, 
        name="Data Science Handbook", 
        category="books", 
        price=59.99, 
        rating=4.6,
        description="Comprehensive data science reference", 
        inventory=75
    ),
    5: Product(
        id=5, 
        name="Smart Watch", 
        category="electronics", 
        price=399.99, 
        rating=4.4,
        description="Advanced fitness and productivity tracker", 
        inventory=30
    ),
    6: Product(
        id=6, 
        name="Coffee Table Book", 
        category="books", 
        price=29.99, 
        rating=4.2,
        description="Beautiful photography collection", 
        inventory=40
    ),
}

@app.get("/health")
async def health_check():
    with tracer.start_as_current_span("health_check") as span:
        span.set_attribute("service.name", SERVICE_NAME)
        span.set_attribute("health.status", "healthy")
        logger.info("Health check requested")
        return {"status": "healthy", "service": SERVICE_NAME}

@app.get("/products", response_model=List[Product])
async def get_products(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of products"),
    skip: int = Query(0, ge=0, description="Number of products to skip")
):
    with tracer.start_as_current_span("get_products") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("products.category", category or "all")
        span.set_attribute("products.limit", limit)
        span.set_attribute("products.skip", skip)
        
        logger.info("Fetching products", category=category, limit=limit, skip=skip)
        
        products = list(products_db.values())
        
        if category:
            products = [p for p in products if p.category == category]
            span.add_event("products_filtered", {"category": category, "count": len(products)})
        
        total_products = len(products)
        products = products[skip:skip + limit]
        
        span.set_attribute("products.total_available", total_products)
        span.set_attribute("products.returned", len(products))
        span.add_event("products_retrieved", {"count": len(products), "total": total_products})
        span.set_status(Status(StatusCode.OK))
        
        logger.info("Products retrieved successfully", 
                   returned=len(products), 
                   total=total_products)
        
        return products

@app.get("/products/recommend", response_model=List[Product])
async def recommend_products(
    request: Request,
    category: str = Query("general", description="Category for recommendations"),
    limit: int = Query(5, ge=1, le=20, description="Number of recommendations")
):
    parent_context = extract(dict(request.headers))
    
    with tracer.start_as_current_span("recommend_products", context=parent_context) as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("recommendation.category", category)
        span.set_attribute("recommendation.limit", limit)
        
        logger.info("Generating product recommendations", 
                   category=category, 
                   limit=limit)
        
        await asyncio.sleep(0.1)
        
        products = list(products_db.values())
        
        if category and category != "general":
            products = [p for p in products if p.category == category]
            span.add_event("products_filtered_by_category", {
                "category": category, 
                "filtered_count": len(products)
            })
        
        if not products:
            logger.warning("No products found for category", category=category)
            span.add_event("no_products_found", {"category": category})
            return []
        
        products.sort(key=lambda x: x.rating, reverse=True)
        recommended_products = products[:limit]
        
        for i, product in enumerate(recommended_products):
            span.add_event(f"product_recommended_{i+1}", {
                "product.id": product.id,
                "product.name": product.name,
                "product.rating": product.rating,
                "product.price": product.price
            })
        
        span.set_attribute("recommendation.count", len(recommended_products))
        span.set_attribute("recommendation.average_rating", 
                          sum(p.rating for p in recommended_products) / len(recommended_products))
        span.set_status(Status(StatusCode.OK))
        
        logger.info("Product recommendations generated", 
                   category=category, 
                   count=len(recommended_products),
                   avg_rating=sum(p.rating for p in recommended_products) / len(recommended_products))
        
        return recommended_products

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: int, request: Request):
    with tracer.start_as_current_span("get_product") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("product.id", product_id)
        
        logger.info("Fetching product", product_id=product_id)
        
        if product_id not in products_db:
            span.record_exception(HTTPException(status_code=404, detail="Product not found"))
            span.set_status(Status(StatusCode.ERROR, "Product not found"))
            logger.warning("Product not found", product_id=product_id)
            raise HTTPException(status_code=404, detail="Product not found")
        
        product = products_db[product_id]
        span.add_event("product_found", {
            "product.name": product.name,
            "product.category": product.category,
            "product.price": product.price
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info("Product retrieved successfully", 
                   product_id=product_id, 
                   product_name=product.name)
        
        return product

@app.post("/products", response_model=Product, status_code=201)
async def create_product(product_data: ProductCreate, request: Request):
    with tracer.start_as_current_span("create_product") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "POST")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("product.name", product_data.name)
        span.set_attribute("product.category", product_data.category)
        span.set_attribute("product.price", product_data.price)
        
        logger.info("Creating new product", 
                   product_name=product_data.name, 
                   category=product_data.category,
                   price=product_data.price)
        
        new_id = max(products_db.keys()) + 1 if products_db else 1
        new_product = Product(
            id=new_id, 
            rating=0.0,  # New products start with no rating
            **product_data.model_dump()
        )
        products_db[new_id] = new_product
        
        span.add_event("product_created", {
            "product.id": new_id,
            "product.name": new_product.name,
            "product.category": new_product.category
        })
        span.set_status(Status(StatusCode.OK))
        
        logger.info("Product created successfully", 
                   product_id=new_id, 
                   product_name=new_product.name)
        
        return new_product

@app.get("/products/category/{category_name}", response_model=List[Product])
async def get_products_by_category(
    category_name: str, 
    request: Request,
    limit: int = Query(10, ge=1, le=100)
):
    with tracer.start_as_current_span("get_products_by_category") as span:
        span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
        span.set_attribute(SpanAttributes.HTTP_URL, str(request.url))
        span.set_attribute("category.name", category_name)
        span.set_attribute("products.limit", limit)
        
        logger.info("Fetching products by category", category=category_name, limit=limit)
        
        products = [p for p in products_db.values() if p.category == category_name]
        
        if not products:
            span.add_event("no_products_in_category", {"category": category_name})
            logger.info("No products found in category", category=category_name)
            return []
        
        products = products[:limit]
        
        span.set_attribute("products.count", len(products))
        span.add_event("products_found", {"category": category_name, "count": len(products)})
        span.set_status(Status(StatusCode.OK))
        
        logger.info("Products found in category", 
                   category=category_name, 
                   count=len(products))
        
        return products

@app.get("/categories")
async def get_categories():
    with tracer.start_as_current_span("get_categories") as span:
        span.set_attribute("operation", "get_categories")
        
        categories = list(set(p.category for p in products_db.values()))
        category_counts = {}
        
        for category in categories:
            count = len([p for p in products_db.values() if p.category == category])
            category_counts[category] = count
        
        span.set_attribute("categories.count", len(categories))
        span.add_event("categories_computed", {"categories": categories})
        span.set_status(Status(StatusCode.OK))
        
        logger.info("Categories retrieved", 
                   categories=categories, 
                   counts=category_counts)
        
        return {
            "categories": categories,
            "category_counts": category_counts
        }

@app.get("/metrics")
async def get_metrics():
    with tracer.start_as_current_span("get_metrics") as span:
        span.set_attribute("metrics.type", "application")
        
        total_products = len(products_db)
        total_inventory = sum(p.inventory for p in products_db.values())
        avg_price = sum(p.price for p in products_db.values()) / total_products if total_products > 0 else 0
        avg_rating = sum(p.rating for p in products_db.values()) / total_products if total_products > 0 else 0
        
        metrics = {
            "service": SERVICE_NAME,
            "products_count": total_products,
            "total_inventory": total_inventory,
            "average_price": round(avg_price, 2),
            "average_rating": round(avg_rating, 2),
            "uptime": "running",
            "version": "1.0.0"
        }
        
        span.add_event("metrics_collected", metrics)
        logger.info("Metrics collected", **metrics)
        
        return metrics

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)