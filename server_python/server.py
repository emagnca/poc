# Try this import order in server.py:
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Path, Query, Request, Response, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Optional, Dict, Any, List
from datetime import datetime

import json
import logging
import traceback

# Import models first
from models import SigningService, Signer, SigningResponse, DocumentStatus, SigningMode, SignatureCreate, UserInDB, Signature

# Then database
from database import get_database, connect_to_mongo, close_mongo_connection
import crud

# Then auth (after models)
from auth import get_current_active_user, get_current_admin_user

# Then routes
from routes.database import router as db_router
from routes.auth import router as auth_router
from routes.selfsign import router as selfsign_router

# Then your service imports
import scrive
import webbrowser
from scrive import BASE_URL
from docusign import DocuSignService
from docusign_oauth import DocuSignOAuth


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

# API Endpoints
@app.post("/api/{service}/sign", response_model=SigningResponse)
async def initiate_signing_process(
        service: str = Path(..., description="Signing service (scrive or docusign)"),
        document: UploadFile = File(..., description="PDF document to be signed"),
        signers: str = Form(..., description="JSON array of signers with email, name, and mode"),
        metadata: str = Form(None, description="Optional metadata as JSON string"),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Initiate the document signing process with specified service and multiple signers

    - **service**: Signing service provider (scrive or docusign)
    - **document**: PDF file to be signed
    - **signers**: JSON string containing array of signer objects
      Example: '[{"signer_email":"john@example.com","signer_name":"John Doe","mode":"DIRECT_SIGNING"}]'
    """
    try:
        # Validate service
        validated_service = validate_service(service)
        metadata_data = json.loads(metadata) if metadata else {}

        # Parse signers JSON
        try:
            signers_data = json.loads(signers)
            # Validate each signer using Pydantic
            signer_objects = [Signer(**signer) for signer in signers_data]
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format for signers")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid signer data: {str(e)}")

        if not signer_objects:
            raise HTTPException(status_code=400, detail="At least one signer is required")

        logger.info(f"Initiating signing process with {validated_service.value} service for {len(signer_objects)} signers")

        # Validate file type
        if not document.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Validate file size (e.g., max 10MB)
        file_content = await document.read()
        if len(file_content) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="File size too large (max 10MB)")

        # Reset file pointer for processing
        await document.seek(0)

        print(signer_objects)

        # Route to appropriate service
        if validated_service == SigningService.SCRIVE:
            # TODO: Integrate with Scrive service for multiple signers
            # result = scrive_service.initiate_signing_process(document, signer_objects)

            # Mock response with multiple signing URLs
            signing_urls = []
            signer_data = scrive.initiate_signing_process(file_content, signer_objects, metadata_data)
            for i, signer in enumerate(signer_data[1]):
                signing_url = signer.get('signing_url')
                signing_urls.append({
                    "signer_email": signer.get('signer_email'),
                    "signing_url": BASE_URL + signing_url if signing_url else '',
                })

            response = SigningResponse(
                document_id=signer_data[0],
                signing_urls=signing_urls,
                service="scrive"
            )

        elif validated_service == SigningService.DOCUSIGN:
            # TODO: Integrate with DocuSign service for multiple signers
            # result = docusign_service.initiate_signing_process(document, signer_objects)

            # Mock response with multiple signing URLs
            signing_urls = []
            for i, signer in enumerate(signer_objects):
                signing_urls.append({
                    "signer_email": signer.signer_email,
                    "signer_name": signer.signer_name,
                    "signing_url": f"https://demo.docusign.net/signing/startinsession.aspx?t=env123_signer{i+1}",
                    "mode": signer.mode
                })

            r = docusign.initiate_signing_process(file_content, signer_objects, metadata_data)
            print("Create signing response")
            response = SigningResponse(
                document_id=r.get('document_id'),
                signing_urls=r.get('signing_urls'),
                service="docusign"
            )
            print("SigningResposne created")

        # After successful signing, store signatures in MongoDB
        for signer_url in response.signing_urls:
            # Find the corresponding signer object
            signer_obj = next((s for s in signer_objects if s.signer_email == signer_url["signer_email"]), None)
            if signer_obj:
                print("Storing signature")
                signature_data = SignatureCreate(
                    document_id=response.document_id,
                    signature_request_id=response.document_id,
                    user_id=current_user.id,
                    signer_email=signer_obj.signer_email,
                    signer_name=signer_obj.signer_name,
                    service=service,
                    status="sent",
                    signing_url=signer_url.get("signing_url"),
                    metadata=metadata_data
                )
                print("Storing in db")

                # Store in MongoDB
                await crud.create_signature(db=db, signature=signature_data)

        logger.info(f"Successfully created signing document with {validated_service.value}: {response.document_id}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating signing process: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

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

@app.put("/api/signatures/{signature_id}/status")
async def update_signature_status(
        signature_id: str,
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a specific signature's status from the external service"""
    try:
        if not ObjectId.is_valid(signature_id):
            raise HTTPException(status_code=400, detail="Invalid signature ID")

        # Get the signature from database
        signature = await db.signatures.find_one({
            "_id": ObjectId(signature_id),
            "user_id": current_user.id
        })

        if not signature:
            raise HTTPException(status_code=404, detail="Signature not found")

        # Get status from external service
        service = signature["service"]
        document_id = signature["document_id"]

        if service == "scrive":
            status_data = scrive.get_document_status(document_id)
        elif service == "docusign":
            status_data = docusign.get_document_status(document_id)
        else:
            raise HTTPException(status_code=400, detail="Unsupported service")

        # Update the signature
        update_result = await db.signatures.update_one(
            {"_id": ObjectId(signature_id)},
            {
                "$set": {
                    "status": status_data.get("status", "unknown"),
                    "signed": status_data.get("signed", False),
                    "updated_at": datetime.utcnow(),
                    "last_status_check": datetime.utcnow(),
                    "external_status_data": status_data
                }
            }
        )

        if update_result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Signature not updated")

        # Return updated signature
        updated_signature = await db.signatures.find_one({"_id": ObjectId(signature_id)})
        updated_signature = convert_objectids_to_strings(updated_signature)

        return Signature(**updated_signature)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating signature status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/{service}/documents/{document_id}/download")
async def download_signed_document(
        service: str = Path(..., description="Signing service (scrive or docusign)"),
        document_id: str = Path(..., description="Document ID"),
        current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Download the signed document from specified service

    - **service**: Signing service provider (scrive or docusign)
    - **document_id**: The ID of the document to download
    """
    try:
        # Validate service
        validated_service = validate_service(service)

        logger.info(f"Download request for document: {document_id} from {validated_service.value}")

        # Route to appropriate service
        if validated_service == SigningService.SCRIVE:

            # Download the signed document from Scrive
            document_content = scrive.get_document(document_id)

            # Return the document as a file download
            return Response(
                content=document_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=signed_document_{document_id}.pdf"
                }
            )

        elif validated_service == SigningService.DOCUSIGN:
            document_content = docusign.get_signed_document(document_id)
            return Response(
                content=document_content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=signed_document_{document_id}.pdf"
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error downloading document: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
