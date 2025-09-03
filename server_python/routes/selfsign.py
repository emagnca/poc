import os
import glob
import json
import sys
import tempfile
import asyncio
import concurrent.futures
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Path, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_database
from auth import get_current_active_user
from models import UserInDB, Signer, SignatureCreate
import crud
from services.selfsign import selfsign
import logging

from bson import ObjectId

import traceback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/selfsignxxx", tags=["selfsignxxx"])


@router.post("/sign")
async def selfsign_document(
        document: UploadFile = File(...),
        signers: str = Form(...),
        metadata: str = Form(None),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Self-sign document using internal certificates"""
    try:
        # Parse signers
        signer_objects = [Signer(**signer) for signer in json.loads(signers)]

        # Parse metadata
        metadata_dict = json.loads(metadata) if metadata else {}

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await document.read()
            temp_file.write(content)
            temp_path = temp_file.name

        try:
            # Run signing in thread pool to avoid event loop conflict
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    selfsign.sign_document,
                    temp_path,
                    [signer.dict() for signer in signer_objects],
                    metadata_dict
                )

            # Store signatures in database (rest of the code remains the same)
            for signer_obj in signer_objects:
                signature_data = SignatureCreate(
                    document_id=response["document_id"],
                    signature_request_id=response["document_id"],
                    user_id=current_user.id,
                    signer_email=signer_obj.signer_email,
                    signer_name=signer_obj.signer_name,
                    service="selfsign",
                    status="completed",
                    signing_url=None,
                    metadata=metadata_dict
                )

                await crud.create_signature(db=db, signature=signature_data)

            return response

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        logger.error(f"Error in self-signing: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Self-signing failed: {str(e)}")


@router.get("/documents/{document_id}/statusxxx")
async def get_selfsign_document_status(
        document_id: str = Path(..., description="Document ID"),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get self-signed document status"""
    try:
        # Verify user has access to this document
        signature = await db.signatures.find_one({
            "document_id": document_id,
            "user_id": current_user.id,
            "service": "selfsign"
        })

        if not signature:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        # Get status from selfsign service
        status_data = selfsign.get_document_status(document_id)

        # Update database with current status
        await db.signatures.update_many(
            {
                "document_id": document_id,
                "user_id": current_user.id,
                "service": "selfsign"
            },
            {
                "$set": {
                    "status": status_data.get("status", "completed"),
                    "signed": status_data.get("signed", True),
                    "updated_at": datetime.utcnow(),
                    "last_status_check": datetime.utcnow()
                }
            }
        )

        return status_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting selfsign document status: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/documents/{document_id}/downloadxxx")
async def download_signed_document(
        document_id: str,
        current_user: UserInDB = Depends(get_current_active_user)
):
    """Download signed document by ID"""
    try:
        # Try to find the document locally first
        local_paths = [
            f"signed_documents/{document_id}.pdf",  # Direct ID match
            f"signed_documents/self_{document_id}.pdf"  # With self prefix
        ]

        # Also check for files that contain the document_id

        pattern_paths = glob.glob(f"signed_documents/*{document_id}*.pdf")
        local_paths.extend(pattern_paths)

        for local_path in local_paths:
            if os.path.exists(local_path):
                return FileResponse(
                    local_path,
                    media_type='application/pdf',
                    filename=f"signed_document_{document_id}.pdf"
                )

        raise HTTPException(status_code=404, detail="Document not found")

    except Exception as e:
        logger.error(f"Error downloading document {document_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/documents/{document_id}/validatexxx")
async def validate_selfsign_document(
        document_id: str = Path(..., description="Document ID"),
        current_user: UserInDB = Depends(get_current_active_user),
        db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Validate self-signed document for DSS compatibility"""
    try:
        # Verify user has access to this document
        signature = await db.signatures.find_one({
            "document_id": document_id,
            "user_id": current_user.id,
            "service": "selfsign"
        })

        if not signature:
            raise HTTPException(status_code=404, detail="Document not found or access denied")

        # Validate document
        validation_result = selfsign.validate_document(document_id)

        return validation_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating selfsign document: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
