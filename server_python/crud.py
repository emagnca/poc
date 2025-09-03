# crud.py
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import UserCreate, UserUpdate, UserInDB, User, SignatureCreate, SignatureUpdate, SignatureInDB, Signature
from passlib.context import CryptContext
from bson import ObjectId
from datetime import datetime
from typing import Optional, List, Dict, Any
import pymongo

from auth import get_password_hash


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Add this function to the top of your crud.py file
from bson import ObjectId

# Update your convert_objectids_to_strings function in crud.py
from bson import ObjectId

def convert_objectids_to_strings(doc):
    """Convert ObjectId fields to strings for Pydantic compatibility"""
    if not doc:
        return doc

    # Make a copy to avoid modifying original
    result = {}

    for key, value in doc.items():
        if isinstance(value, ObjectId):
            result[key] = str(value)
        else:
            result[key] = value

    return result




# User CRUD operations
async def create_user(db: AsyncIOMotorDatabase, user: UserCreate) -> UserInDB:
    from auth import get_password_hash  # Make sure this import is at the top

    hashed_password = get_password_hash(user.password)
    user_dict = user.dict()
    user_dict.pop("password")
    user_dict["hashed_password"] = hashed_password
    user_dict["created_at"] = datetime.utcnow()

    result = await db.users.insert_one(user_dict)
    created_user = await db.users.find_one({"_id": result.inserted_id})

    # Convert ObjectId to string
    created_user = convert_objectids_to_strings(created_user)
    return UserInDB(**created_user)

async def get_user_by_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[UserInDB]:
    if not ObjectId.is_valid(user_id):
        return None
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        return UserInDB(**user)
    return None

async def get_user_by_email(db: AsyncIOMotorDatabase, email: str) -> Optional[UserInDB]:
    user = await db.users.find_one({"email": email})
    if user:
        # Explicitly convert ObjectId to string
        if "_id" in user:
            user["_id"] = str(user["_id"])
        if "user_id" in user and isinstance(user["user_id"], ObjectId):
            user["user_id"] = str(user["user_id"])

        return UserInDB(**user)
    return None

async def get_users(db: AsyncIOMotorDatabase, skip: int = 0, limit: int = 100) -> List[User]:
    cursor = db.users.find().skip(skip).limit(limit).sort("created_at", pymongo.DESCENDING)
    users = []
    async for user in cursor:
        users.append(User(**user))
    return users

async def update_user(db: AsyncIOMotorDatabase, user_id: str, user_update: UserUpdate) -> Optional[User]:
    if not ObjectId.is_valid(user_id):
        return None

    update_data = {k: v for k, v in user_update.dict().items() if v is not None}
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )

    updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if updated_user:
        return User(**updated_user)
    return None

async def delete_user(db: AsyncIOMotorDatabase, user_id: str) -> bool:
    if not ObjectId.is_valid(user_id):
        return False

    result = await db.users.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0

# Signature CRUD operations
# In crud.py, update functions like this:

async def create_signature(db: AsyncIOMotorDatabase, signature: SignatureCreate) -> SignatureInDB:
    signature_dict = signature.dict()
    current_time = datetime.utcnow()
    signature_dict["updated_at"] = current_time

    # Use upsert to prevent duplicates based on document_id, signer_email, user_id, and service
    result = await db.signatures.update_one(
        {
            "document_id": signature_dict["document_id"],
            "signer_email": signature_dict["signer_email"],
            "user_id": signature_dict["user_id"],
            "service": signature_dict["service"]
        },
        {
            "$set": signature_dict,
            "$setOnInsert": {"created_at": current_time}
        },
        upsert=True
    )

    # Get the signature (either updated or newly created)
    if result.upserted_id:
        # New document was created
        signature_id = result.upserted_id
    else:
        # Existing document was updated, find it by the filter criteria
        existing_signature = await db.signatures.find_one({
            "document_id": signature_dict["document_id"],
            "signer_email": signature_dict["signer_email"],
            "user_id": signature_dict["user_id"],
            "service": signature_dict["service"]
        })
        signature_id = existing_signature["_id"]

    # Retrieve the final signature
    created_signature = await db.signatures.find_one({"_id": signature_id})

    # Convert ObjectId to string
    if created_signature:
        created_signature = convert_objectids_to_strings(created_signature)

    return SignatureInDB(**created_signature)



# Apply similar fixes to other functions:
async def get_signature_by_id(db: AsyncIOMotorDatabase, signature_id: str) -> Optional[Signature]:
    if not ObjectId.is_valid(signature_id):
        return None

    signature = await db.signatures.find_one({"_id": ObjectId(signature_id)})
    if signature:
        # Convert ObjectIds to strings
        signature["_id"] = str(signature["_id"])
        if "user_id" in signature and isinstance(signature["user_id"], ObjectId):
            signature["user_id"] = str(signature["user_id"])
        return Signature(**signature)
    return None



async def get_signatures_by_document(db: AsyncIOMotorDatabase, document_id: str) -> List[Signature]:
    cursor = db.signatures.find({"document_id": document_id}).sort("created_at", pymongo.DESCENDING)
    signatures = []
    async for signature in cursor:
        signatures.append(Signature(**signature))
    return signatures

async def get_signatures_by_user(db: AsyncIOMotorDatabase, user_id: str) -> List[Signature]:
    if not ObjectId.is_valid(user_id):
        return []

    cursor = db.signatures.find({"user_id": ObjectId(user_id)}).sort("created_at", pymongo.DESCENDING)
    signatures = []
    async for signature in cursor:
        signatures.append(Signature(**signature))
    return signatures

async def get_signatures_by_request(db: AsyncIOMotorDatabase, signature_request_id: str) -> List[Signature]:
    cursor = db.signatures.find({"signature_request_id": signature_request_id}).sort("created_at", pymongo.DESCENDING)
    signatures = []
    async for signature in cursor:
        signatures.append(Signature(**signature))
    return signatures

async def update_signature(db: AsyncIOMotorDatabase, signature_id: str, signature_update: SignatureUpdate) -> Optional[Signature]:
    if not ObjectId.is_valid(signature_id):
        return None

    update_data = {k: v for k, v in signature_update.dict().items() if v is not None}
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.signatures.update_one(
            {"_id": ObjectId(signature_id)},
            {"$set": update_data}
        )

    updated_signature = await db.signatures.find_one({"_id": ObjectId(signature_id)})
    if updated_signature:
        return Signature(**updated_signature)
    return None

async def search_signatures(
        db: AsyncIOMotorDatabase,
        user_id: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        signer_email: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
) -> List[Signature]:
    query = {}

    if user_id and ObjectId.is_valid(user_id):
        query["user_id"] = ObjectId(user_id)
    if service:
        query["service"] = service
    if status:
        query["status"] = status
    if signer_email:
        query["signer_email"] = {"$regex": signer_email, "$options": "i"}

    cursor = db.signatures.find(query).skip(skip).limit(limit).sort("created_at", pymongo.DESCENDING)
    signatures = []
    async for signature in cursor:
        signatures.append(Signature(**signature))
    return signatures

# Advanced queries using MongoDB aggregation
async def get_user_with_signatures(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Dict[str, Any]]:
    if not ObjectId.is_valid(user_id):
        return None

    pipeline = [
        {"$match": {"_id": ObjectId(user_id)}},
        {
            "$lookup": {
                "from": "signatures",
                "localField": "_id",
                "foreignField": "user_id",
                "as": "signatures"
            }
        }
    ]

    async for result in db.users.aggregate(pipeline):
        return result
    return None

async def get_signature_stats(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }
        }
    ]

    stats = {}
    async for result in db.signatures.aggregate(pipeline):
        stats[result["_id"]] = result["count"]

    return stats


async def create_user(db: AsyncIOMotorDatabase, user: UserCreate) -> UserInDB:
    hashed_password = get_password_hash(user.password)  # Use auth.py function
    user_dict = user.dict()
    user_dict.pop("password")
    user_dict["hashed_password"] = hashed_password
    user_dict["created_at"] = datetime.utcnow()

    result = await db.users.insert_one(user_dict)
    created_user = await db.users.find_one({"_id": result.inserted_id})

    # Convert ObjectId to string
    created_user = convert_objectids_to_strings(created_user)
    return UserInDB(**created_user)
