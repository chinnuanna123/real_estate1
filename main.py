from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import home_buying_routes
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="AI Home Buying Assistant Backend",
    description="An API for an end-to-end property buying assistant.",
    version="0.1.0",
)

# Configure CORS to allow requests from your React frontend
# In a production environment, replace "*" with your React app's domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Include your API routes
app.include_router(home_buying_routes.router, prefix="/api/v1/home_buying")

@app.get("/")
async def root():
    return {"message": "AI Home Buying Assistant Backend is running!"}