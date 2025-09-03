from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from bson import ObjectId
from enum import Enum

class SigningService(str, Enum):
    SCRIVE = "scrive"
    DOCUSIGN = "docusign"

class SigningMode(str, Enum):
    DIRECT_SIGNING = "DIRECT_SIGNING"
    EMAIL_NOTIFICATION = "EMAIL_NOTIFICATION"

class Signer(BaseModel):
    signer_email: EmailStr
    signer_name: str
    mode: SigningMode = SigningMode.DIRECT_SIGNING

class SigningResponse(BaseModel):
    document_id: str
    signing_urls: List[dict]  # List of {signer_email, signing_url}
    service: str

class DocumentStatus(BaseModel):
    document_id: str
    status: str
    signed: bool
    service: str
    signers: List[dict]

# Simplified ObjectId handling for Pydantic v2
def validate_object_id(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, str):
        if ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid ObjectId")
    raise ValueError("ObjectId must be a valid ObjectId or string")

PyObjectId = Annotated[str, Field(validation_alias="validate_object_id")]

# User models
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    is_active: bool = True
    is_admin: bool = False

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserInDB(UserBase):
    id: str = Field(alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class User(UserBase):
    id: str = Field(alias="_id")
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

# Signature models
class SignatureBase(BaseModel):
    document_id: str
    signature_request_id: str
    signer_email: EmailStr
    signer_name: str
    service: str  # 'scrive' or 'docusign'
    status: str = "pending"  # pending, sent, signed, completed, failed
    signing_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class SignatureCreate(SignatureBase):
    user_id: str

class SignatureUpdate(BaseModel):
    status: Optional[str] = None
    signing_url: Optional[str] = None
    signed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class SignatureInDB(SignatureBase):
    id: str = Field(alias="_id")
    user_id: str
    signed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str}
    )

class Signature(BaseModel):
    id: str = Field(alias="_id")
    document_id: str
    signature_request_id: str
    user_id: str
    signer_email: str
    signer_name: str
    service: str
    status: str
    signed: bool = False
    signing_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_status_check: Optional[datetime] = None
    external_status_data: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None  # Add this
    deleted_by: Optional[str] = None  # Add this
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, datetime: str}
    )


# Combined models
class UserWithSignatures(User):
    signatures: List[Signature] = []

class SignatureWithUser(Signature):
    user: Optional[User] = None

# Login related
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime