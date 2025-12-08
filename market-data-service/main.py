from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app, Counter, Gauge
import psutil
import os
from contextlib import asynccontextmanager

# Get service name from environment variable or use directory name
SERVICE_NAME = os.getenv('SERVICE_NAME', os.path.basename(os.getcwd()))

# Metrics
REQUEST_COUNTER = Counter(
    f"{SERVICE_NAME}_requests_total",
    "Total number of requests",
    ["endpoint", "method"]
)
ERROR_COUNTER = Counter(
    f"{SERVICE_NAME}_errors_total",
    "Total number of errors",
    ["endpoint", "method", "error_code"]
)
REQUEST_LATENCY = Gauge(
    f"{SERVICE_NAME}_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint", "method"]
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting {SERVICE_NAME} service")
    yield
    # Shutdown
    print(f"Shutting down {SERVICE_NAME} service")

app = FastAPI(lifespan=lifespan)

# Add prometheus asgi middleware to route /metrics requests
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": "1.0.0"
    }

# System metrics endpoint
@app.get("/system-metrics")
async def system_metrics():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage('/').percent
    }

# Example endpoint
@app.get("/")
async def root():
    REQUEST_COUNTER.labels(endpoint="/", method="GET").inc()
    return {
        "message": f"Hello from {SERVICE_NAME} service",
        "status": "running"
    }
