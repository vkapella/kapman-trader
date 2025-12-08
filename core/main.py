from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from typing import List, Optional
from pydantic import BaseModel
import uvicorn

# Create FastAPI app
app = FastAPI(title="Kapman Core Service", version="0.1.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "kapman-core"}

# Example endpoint
@app.get("/api/v1/hello")
async def hello_world():
    return {"message": "Hello from Kapman Core!"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
