# database.py
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING
import os
from typing import Optional

class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    database = None

# MongoDB connection
mongodb_client = MongoDB()

# MongoDB connection string - adjust as needed
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "document_signing")

async def connect_to_mongo():
    """Create database connection"""
    mongodb_client.client = AsyncIOMotorClient(MONGODB_URL)
    mongodb_client.database = mongodb_client.client[DATABASE_NAME]

    # Create indexes for better performance
    await create_indexes()
    print(f"Connected to MongoDB at {MONGODB_URL}")

async def close_mongo_connection():
    """Close database connection"""
    if mongodb_client.client:
        mongodb_client.client.close()
        print("Disconnected from MongoDB")

async def create_indexes():
    """Create database indexes"""
    users_collection = mongodb_client.database.users
    signatures_collection = mongodb_client.database.signatures

    # User indexes
    await users_collection.create_index([("email", ASCENDING)], unique=True)
    await users_collection.create_index([("created_at", ASCENDING)])

    # Signature indexes
    await signatures_collection.create_index([("document_id", ASCENDING)])
    await signatures_collection.create_index([("signature_request_id", ASCENDING)])
    await signatures_collection.create_index([("user_id", ASCENDING)])
    await signatures_collection.create_index([("signer_email", ASCENDING)])
    await signatures_collection.create_index([("service", ASCENDING)])
    await signatures_collection.create_index([("status", ASCENDING)])
    await signatures_collection.create_index([("created_at", ASCENDING)])

def get_database():
    """Get database instance"""
    return mongodb_client.database
