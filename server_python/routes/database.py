# routes/database.py
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from database import get_database
from models import User, UserCreate, UserUpdate, Signature, SignatureCreate, SignatureUpdate
import crud

router = APIRouter(prefix="/api/db", tags=["database"])

# User endpoints
@router.post("/users/", response_model=User)
async def create_user(user: UserCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    # Check if user already exists
    existing_user = await crud.get_user_by_email(db, email=user.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    created_user = await crud.create_user(db=db, user=user)
    return User(**created_user.dict())

@router.get("/users/", response_model=List[User])
async def read_users(skip: int = 0, limit: int = 100, db: AsyncIOMotorDatabase = Depends(get_database)):
    users = await crud.get_users(db, skip=skip, limit=limit)
    return users

@router.get("/users/{user_id}", response_model=User)
async def read_user(user_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    user = await crud.get_user_by_id(db, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return User(**user.dict())

@router.get("/users/{user_id}/with-signatures")
async def read_user_with_signatures(user_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    user_data = await crud.get_user_with_signatures(db, user_id=user_id)
    if user_data is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user_data

@router.put("/users/{user_id}", response_model=User)
async def update_user(user_id: str, user_update: UserUpdate, db: AsyncIOMotorDatabase = Depends(get_database)):
    user = await crud.update_user(db, user_id=user_id, user_update=user_update)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    success = await crud.delete_user(db, user_id=user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

# Signature endpoints
@router.post("/signatures/", response_model=Signature)
async def create_signature(signature: SignatureCreate, db: AsyncIOMotorDatabase = Depends(get_database)):
    # Verify user exists
    user = await crud.get_user_by_id(db, user_id=str(signature.user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    created_signature = await crud.create_signature(db=db, signature=signature)
    return Signature(**created_signature.dict())

@router.get("/signatures/", response_model=List[Signature])
async def read_signatures(
        user_id: Optional[str] = Query(None),
        service: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        signer_email: Optional[str] = Query(None),
        skip: int = 0,
        limit: int = 100,
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    signatures = await crud.search_signatures(
        db,
        user_id=user_id,
        service=service,
        status=status,
        signer_email=signer_email,
        skip=skip,
        limit=limit
    )
    return signatures

@router.get("/signatures/{signature_id}", response_model=Signature)
async def read_signature(signature_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    signature = await crud.get_signature_by_id(db, signature_id=signature_id)
    if signature is None:
        raise HTTPException(status_code=404, detail="Signature not found")
    return signature

@router.put("/signatures/{signature_id}", response_model=Signature)
async def update_signature(signature_id: str, signature_update: SignatureUpdate, db: AsyncIOMotorDatabase = Depends(get_database)):
    signature = await crud.update_signature(db, signature_id=signature_id, signature_update=signature_update)
    if signature is None:
        raise HTTPException(status_code=404, detail="Signature not found")
    return signature

@router.get("/signatures/document/{document_id}", response_model=List[Signature])
async def read_signatures_by_document(document_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await crud.get_signatures_by_document(db, document_id=document_id)

@router.get("/signatures/request/{signature_request_id}", response_model=List[Signature])
async def read_signatures_by_request(signature_request_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await crud.get_signatures_by_request(db, signature_request_id=signature_request_id)

@router.get("/signatures/user/{user_id}", response_model=List[Signature])
async def read_signatures_by_user(user_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    return await crud.get_signatures_by_user(db, user_id=user_id)

@router.get("/stats/signatures")
async def get_signature_statistics(db: AsyncIOMotorDatabase = Depends(get_database)):
    stats = await crud.get_signature_stats(db)
    return {"signature_stats": stats}
