# server.py

# Standard library imports
import asyncio
import concurrent.futures
import json
import logging
import os
import tempfile
import traceback
import webbrowser
from datetime import datetime
from typing import Optional, Dict, Any, List

# Third-party imports
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Path, Query, Request, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

# Local imports - Models
from models import (
    SigningService,
    Signer,
    SigningResponse,
    DocumentStatus,
    SigningMode,
    SignatureCreate,
    UserInDB,
    Signature
)

# Local imports - Database
from database import get_database, connect_to_mongo, close_mongo_connection
import crud

# Local imports - Authentication
from auth import get_current_active_user, get_current_admin_user

# Local imports - Routes
from routes.database import router as db_router
from routes.auth import router as auth_router
from routes.selfsign import router as selfsign_router

# Local imports - Services
import scrive
from scrive import BASE_URL
from docusign import DocuSignService
from docusign_oauth import DocuSignOAuth
from services.selfsign import selfsign




# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

docusign_oauth = DocuSignOAuth()
docusign = DocuSignService(docusign_oauth)

app = FastAPI(
    title="Document Signing API",
    description="API for document signing with multiple service providers",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

app.include_router(auth_router)
app.include_router(db_router)
app.include_router(selfsign_router)

# Database connection events
@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()
    print("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()
    print("Application shutdown complete")

# Service validation function
def validate_service(service):
    """Validate and return the signing service"""
    try:
        return SigningService(service.lower())
    except ValueError:
        supported_services = [s.value for s in SigningService]
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported service '{service}'. Supported services: {supported_services}"
        )

@app.post("/api/{service}/sign", response_model=SigningResponse)
async def sign_document(
        service: str,
        document: UploadFile = File(...),
        signers: str = Form(...),
        metadata: str = Form(None),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Universal document signing endpoint for all services"""
    try:
        # Validate service
        if service not in ["scrive", "docusign", "selfsign"]:
            raise HTTPException(status_code=400, detail=f"Unsupported service: {service}")

        # Parse signers and metadata
        signer_objects = [Signer(**signer) for signer in json.loads(signers)]
        metadata_dict = json.loads(metadata) if metadata else {}

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await document.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Route to appropriate service
            if service == "selfsign":
                # Handle self-signing with thread pool to avoid event loop conflict
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    response = await loop.run_in_executor(
                        executor,
                        selfsign.sign_document,
                        temp_path,
                        [signer.dict() for signer in signer_objects],
                        metadata_dict
                    )

            elif service == "scrive":
                from services.scrive import scrive
                response = await scrive.sign_document(
                    temp_path,
                    [signer.dict() for signer in signer_objects],
                    metadata_dict
                )

            elif service == "docusign":
                from services.docusign import docusign
                response = await docusign.sign_document(
                    temp_path,
                    [signer.dict() for signer in signer_objects],
                    metadata_dict
                )

            # Store signatures in database for all services
            for signer_obj in signer_objects:
                signature_data = SignatureCreate(
                    document_id=response["document_id"],
                    signature_request_id=response["document_id"],
                    user_id=current_user.id,
                    signer_email=signer_obj.signer_email,
                    signer_name=signer_obj.signer_name,
                    service=service,
                    status="completed" if service == "selfsign" else "pending",
                    signing_url=None if service == "selfsign" else response.get("signing_urls", [{}])[0].get("signing_url"),
                    metadata=metadata_dict
                )

                await crud.create_signature(db=db, signature=signature_data)

            return response

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        logger.error(f"Error in {service} signing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"{service.title()} signing failed: {str(e)}")

def map_docusign_status(docusign_status: str) -> str:
    return docusign_status.lower()

def map_scrive_status(scrive_status: str) -> str:
    """Map Scrive status to internal status"""
    status_mapping = {
        "pending": "pending",
        "preparation": "pending",
        "sent": "sent",
        "delivered": "sent",
        "opened": "sent",
        "signed": "signed",
        "closed": "completed",  # This is correct - closed documents are completed
        "rejected": "failed",
        "timedout": "failed",
        "expired": "failed",
        "error": "failed"
    }
    return status_mapping.get(scrive_status.lower(), scrive_status.lower())




@app.get("/api/{service}/documents/{document_id}/status")
async def get_document_status(
        service: str = Path(..., description="Signing service (scrive or docusign)"),
        document_id: str = Path(..., description="Document ID"),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    try:
        # Validate service
        if service not in ["scrive", "docusign"]:
            raise HTTPException(status_code=400, detail="Unsupported service")

        # Get status from external service
        if service == "scrive":
            status_data = scrive.get_document_status(document_id)
            mapped_status = map_scrive_status(status_data.get("status", "unknown"))
        elif service == "docusign":
            status_data = docusign.get_signing_status(document_id)
            mapped_status = map_docusign_status(status_data.get("status", "unknown"))
        # Update all signatures for this document in the database
        update_result = await db.signatures.update_many(
            {
                "document_id": document_id,
                "user_id": current_user.id,  # Ensure user can only update their own documents
                "service": service
            },
            {
                "$set": {
                    "status": mapped_status,
                    "signed": status_data.get("signed", False),
                    "updated_at": datetime.utcnow(),
                    "last_status_check": datetime.utcnow(),
                    # Add any other relevant fields from the status response
                    "external_status_data": status_data  # Store the full response for reference
                }
            }
        )

        # Log the update
        logger.info(f"Updated {update_result.modified_count} signatures for document {document_id}")

        # Return the status data along with update info
        return {
            "document_id": document_id,
            "service": service,
            "status": status_data.get("status"),
            "signed": status_data.get("signed"),
            "updated_signatures": update_result.modified_count,
            "last_updated": datetime.utcnow().isoformat(),
            "details": status_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/{service}/documents/{document_id}/download")
async def download_document(
        service: str,
        document_id: str,
        current_user: UserInDB = Depends(get_current_active_user)
):
    """Universal document download endpoint for all services"""
    try:
        # Validate service
        if service not in ["scrive", "docusign", "selfsign"]:
            raise HTTPException(status_code=400, detail=f"Unsupported service: {service}")

        # Route to appropriate service
        if service == "selfsign":
            from services.selfsign import selfsign
            return await selfsign.download_document(document_id)

        elif service == "scrive":
            from services.scrive import scrive
            return await scrive.download_document(document_id)

        elif service == "docusign":
            from services.docusign import docusign
            return await docusign.download_document(document_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document from {service}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.get("/api/{service}/documents/{document_id}/status")
async def get_document_status(
        service: str,
        document_id: str,
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Universal document status endpoint for all services"""
    try:
        # Validate service
        if service not in ["scrive", "docusign", "selfsign"]:
            raise HTTPException(status_code=400, detail=f"Unsupported service: {service}")

        # Route to appropriate service
        if service == "selfsign":
            from services.selfsign import selfsign
            status_data = await selfsign.get_document_status(document_id)

        elif service == "scrive":
            from services.scrive import scrive
            status_data = await scrive.get_document_status(document_id)

        elif service == "docusign":
            from services.docusign import docusign
            status_data = await docusign.get_document_status(document_id)

        # Also get database signatures for additional context
        signatures = await crud.get_signatures_by_document_id(db, document_id)

        # Combine service status with database info
        return {
            **status_data,
            "database_signatures": [
                {
                    "signer_email": sig.signer_email,
                    "signer_name": sig.signer_name,
                    "status": sig.status,
                    "created_at": sig.created_at,
                    "signed_at": sig.signed_at
                } for sig in signatures
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status from {service}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@app.get("/api/{service}/documents/{document_id}")
async def get_document_details(
        service: str,
        document_id: str,
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Universal document details endpoint for all services"""
    try:
        # Validate service
        if service not in ["scrive", "docusign", "selfsign"]:
            raise HTTPException(status_code=400, detail=f"Unsupported service: {service}")

        # Get document status from service
        status_data = await get_document_status(service, document_id, current_user, db)

        # Get signatures from database
        signatures = await crud.get_signatures_by_document_id(db, document_id)

        return {
            "document_id": document_id,
            "service": service,
            "status": status_data.get("status", "unknown"),
            "metadata": status_data.get("metadata", {}),
            "signatures": [
                {
                    "id": str(sig.id),
                    "signer_email": sig.signer_email,
                    "signer_name": sig.signer_name,
                    "status": sig.status,
                    "signing_url": sig.signing_url,
                    "created_at": sig.created_at,
                    "signed_at": sig.signed_at,
                    "metadata": sig.metadata
                } for sig in signatures
            ],
            "download_url": f"/api/{service}/documents/{document_id}/download",
            "created_at": status_data.get("created_at"),
            "completed_at": status_data.get("completed_at")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document details from {service}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Document details failed: {str(e)}")




@app.get("/api/{service}/documents/search")
async def search_documents(
        service: str = Path(..., description="Signing service (scrive or docusign)"),
        handler: Optional[str] = Query(None, description="Filter by handler"),
        system: Optional[str] = Query(None, description="Filter by system"),
        status: Optional[str] = Query(None, description="Filter by document status"),
        title: Optional[str] = Query(None, description="Filter by document title"),
        limit: int = Query(50, description="Maximum number of results", le=100),
        offset: int = Query(0, description="Offset for pagination")
):
    try:
        # Validate service
        validated_service = validate_service(service)

        # Build search parameters
        search_params = {}
        if handler:
            search_params['handler'] = handler
        if system:
            search_params['system'] = system
        if status:
            search_params['status'] = status
        if title:
            search_params['title'] = title

        logger.info(f"Searching documents with {validated_service.value}, params: {search_params}")

        # Route to appropriate service
        if validated_service == SigningService.SCRIVE:
            results = await scrive.search_documents(search_params, limit, offset)
        elif validated_service == SigningService.DOCUSIGN:
            logger.info("Calling docusign search")
            results = await docusign.search_documents(search_params, limit, offset)

        return {
                    "service": service,
                    "results": results,
                    "search_params": search_params,
                    "limit": limit,
                    "offset": offset
                }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/signatures/search")
async def search_signatures(
        handler: Optional[str] = Query(None, description="Handler email or ID"),
        document_id: Optional[str] = Query(None, description="Document ID"),
        signer_email: Optional[str] = Query(None, description="Signer email"),
        status: Optional[str] = Query(None, description="Signature status"),
        service: Optional[str] = Query(None, description="Signing service"),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Search signatures with various criteria"""
    try:
        # Build query filter
        query_filter = {}

        # Always filter by current user (security measure)
        query_filter["user_id"] = current_user.id

        # Always exclude deleted signatures
        query_filter["status"] = {"$ne": "deleted"}

        # Add other filters if provided
        if document_id:
            query_filter["document_id"] = document_id

        if signer_email:
            query_filter["signer_email"] = {"$regex": signer_email, "$options": "i"}

        # Handle status filter more carefully
        if status and status.strip():
            if status == "deleted":
                # Don't allow searching for deleted items
                return {"signatures": [], "total": 0, "query": query_filter}
            else:
                # Override the $ne filter if specific status is requested
                query_filter["status"] = status

        if service:
            query_filter["service"] = service

        # Debug logging
        logger.info(f"Search query: {query_filter}")

        # Search signatures in database
        signatures_cursor = db.signatures.find(query_filter).sort("created_at", -1)
        signatures = await signatures_cursor.to_list(length=100)

        logger.info(f"Found {len(signatures)} signatures")

        # Convert to Pydantic models with proper ObjectId conversion
        signature_objects = []
        for sig in signatures:
            try:
                converted_sig = crud.convert_objectids_to_strings(sig)
                signature_objects.append(Signature(**converted_sig))
            except Exception as e:
                logger.error(f"Error converting signature: {e}")
                logger.error(f"Signature data: {sig}")
                continue

        return {
            "signatures": [sig.dict() for sig in signature_objects],
            "total": len(signature_objects),
            "query": query_filter
        }

    except Exception as e:
        logger.error(f"Error searching signatures: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")





@app.put("/api/signatures/{signature_id}/delete")
async def delete_signature(
        signature_id: str,
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Mark a signature as deleted (soft delete)"""
    try:
        if not ObjectId.is_valid(signature_id):
            raise HTTPException(status_code=400, detail="Invalid signature ID")

        # Update the signature status to deleted
        update_result = await db.signatures.update_one(
            {
                "_id": ObjectId(signature_id),
                "user_id": current_user.id,  # Ensure user can only delete their own signatures
                "status": {"$ne": "deleted"}  # Prevent deleting already deleted signatures
            },
            {
                "$set": {
                    "status": "deleted",
                    "deleted_at": datetime.utcnow(),
                    "deleted_by": current_user.id,
                    "updated_at": datetime.utcnow()
                }
            }
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Signature not found or already deleted")

        logger.info(f"Signature {signature_id} marked as deleted by user {current_user.id}")

        return {
            "message": "Signature deleted successfully",
            "signature_id": signature_id,
            "deleted_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting signature: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# List supported services endpoint
@app.get("/api/services")
async def get_supported_services(current_user: UserInDB = Depends(get_current_active_user)):
    """Get list of supported signing services"""
    return {
        "supported_services": ["scrive", "docusign", "selfsign"],
        "current_user": current_user.email
    }

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "document-signing-api"}

#==================================================================
# Docusign oauth related methods
#==================================================================
#https://account-d.docusign.com/password?response_type=code&scope=signature%20impersonation&client_id=380ba0c6-5812-4e1f-9066-520c6a19ea93&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fauth%2Fdocusign%2Fcallback
@app.get("/auth/docusign/login")
async def docusign_login():
    """Initiate DocuSign OAuth flow"""
    print("Docusign login")
    auth_url = docusign_oauth.get_authorization_url(state="random_state_string")
    print(auth_url)
    webbrowser.open(auth_url)
    #return RedirectResponse(url=auth_url)


@app.get("/auth/docusign/callback")
async def docusign_callback(request: Request):
    """Handle DocuSign OAuth callback"""
    print("Docusign callback")
    try:
        # Get authorization code from query parameters
        code = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')

        if error:
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

        if not code:
            raise HTTPException(status_code=400, detail="No authorization code received")

        # Exchange code for token
        token_data = docusign_oauth.exchange_code_for_token(code)

        logger.info(token_data)

        return {
            "message": "Successfully authenticated with DocuSign",
            "expires_in": token_data.get('expires_in'),
            "token_type": token_data.get('token_type')
        }

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/docusign/status")
async def docusign_auth_status():
    """Check DocuSign authentication status"""
    try:
        token = docusign_oauth.get_valid_access_token()
        return {
            "authenticated": True,
            "expires_at": docusign_oauth.token_expires_at
        }
    except Exception as e:
        return {
            "authenticated": False,
            "error": str(e)
        }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )

#python -m uvicorn server:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
