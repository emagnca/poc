import os
import tempfile
import asyncio
import concurrent.futures
import threading
from functools import partial
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from io import BytesIO
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pyhanko import stamp
from pyhanko.pdf_utils import writer, reader
from pyhanko.sign import signers, fields
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.stamp import TextStampStyle
from pyhanko.pdf_utils.font import opentype
from pyhanko.pdf_utils import misc

import logging, traceback
from bson import ObjectId

from .document_storage import DocumentStorageClient

logger = logging.getLogger(__name__)

class SelfSignService:
    """Self-signing service using pyHanko for DSS-compatible signatures"""

    def __init__(self, storage_server_url: str = "http://localhost:3001",
                 login_server_url: str = "http://localhost:3001",
                 storage_email: str = "ehsmaga@yahoo.se",
                 storage_password: str = "mySecret",
                 storage_code: str = "121212"):
        self.storage_email = storage_email
        self.storage_password = storage_password
        self.storage_code = storage_code
        self.service_name = "selfsign"
        self.cert_store_path = "certificates"
        os.makedirs(self.cert_store_path, exist_ok=True)

        # Initialize document storage client
        self.storage_client = DocumentStorageClient(storage_server_url, login_server_url)

        # Add debugging
        logger.info(f"Storage URL: {storage_server_url}")
        logger.info(f"Storage Email: {storage_email}")
        logger.info(f"Storage Password: {'***' if storage_password else 'None'}")

        # Auto-login if credentials provided
        if storage_email and storage_password:
            logger.info("Attempting to authenticate with document storage...")
            success = self.storage_client.login_usrpwd(storage_email, storage_password, storage_code)
            if success:
                logger.info("Successfully authenticated with document storage")
            else:
                logger.error("Failed to authenticate with document storage service")
        else:
            logger.warning("No storage credentials provided - authentication skipped")

    def ensure_authenticated(self) -> bool:
        """Ensure storage client is authenticated"""
        if not self.storage_client.is_authenticated():
            logger.warning("Document storage client is not authenticated - trying to log in")
            success = self.storage_client.login_usrpwd(self.storage_email, self.storage_password, self.storage_code)
            logger.info("Logged in?" + str(success))
            return success
        return True

    def _generate_certificate(self, signer_name: str, signer_email: str) -> tuple:
        """Generate a self-signed certificate for the signer"""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Create certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "SE"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Stockholm"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Stockholm"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Document Signing Platform"),
            x509.NameAttribute(NameOID.COMMON_NAME, signer_name),
            x509.NameAttribute(NameOID.EMAIL_ADDRESS, signer_email),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.now(timezone.utc)
        ).not_valid_after(
            datetime.now(timezone.utc).replace(year=datetime.now().year + 1)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.RFC822Name(signer_email),
            ]),
            critical=False,
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=True,
                data_encipherment=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.EMAIL_PROTECTION,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=True,
        ).sign(private_key, hashes.SHA256())

        return private_key, cert

    def _get_or_create_signer_cert(self, signer_name: str, signer_email: str) -> signers.SimpleSigner:
        """Get existing certificate or create new one for signer"""
        cert_file = os.path.join(self.cert_store_path, f"{signer_email.replace('@', '_at_').replace('.', '_')}.p12")

        if os.path.exists(cert_file):
            # Load existing certificate using file path
            try:
                return signers.SimpleSigner.load_pkcs12(cert_file, passphrase=b'')
            except Exception as e:
                logger.warning(f"Failed to load existing certificate for {signer_email}: {e}")

        # Generate new certificate
        private_key, cert = self._generate_certificate(signer_name, signer_email)

        # Create PKCS#12 bundle
        p12_data = serialization.pkcs12.serialize_key_and_certificates(
            name=signer_name.encode(),
            key=private_key,
            cert=cert,
            cas=None,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Save certificate to file
        with open(cert_file, 'wb') as f:
            f.write(p12_data)

        # Create signer using file path (not raw data)
        return signers.SimpleSigner.load_pkcs12(cert_file, passphrase=b'')


    def sign_document(self, document_path: str, signers_data: List[Dict], metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """Sign document with multiple signers and return URLs for DIRECT_SIGNING"""
        try:
            # Generate a proper MongoDB ObjectId for document_id
            document_id = str(ObjectId())

            # Keep the custom ID for local storage if needed
            local_document_id = f"self_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash(document_path) % 10000}"

            # Initialize storage variables
            storage_document_id = document_id
            uploaded_to_storage = False

            # Read the original PDF in binary mode
            with open(document_path, 'rb') as f:
                pdf_data = f.read()

            # Create temporary file for processing
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_data)
                temp_path = temp_file.name

            try:
                signing_urls = []

                for i, signer_data in enumerate(signers_data):
                    signer_email = signer_data['signer_email']
                    signer_name = signer_data['signer_name']
                    signer_mode = signer_data.get('mode', 'DIRECT_SIGNING')
                    signing_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

                    # Get or create certificate for signer
                    signer_cert = self._get_or_create_signer_cert(signer_name, signer_email)

                    # Read PDF for signing
                    with open(temp_path, 'rb') as f:
                        pdf_bytes = f.read()

                    pdf_stream = BytesIO(pdf_bytes)

                    try:
                        pdf_reader = reader.PdfFileReader(pdf_stream)
                        pdf_writer = writer.copy_into_new_writer(pdf_reader)
                    except Exception as e:
                        logger.error(f"Error reading PDF with BytesIO: {e}")
                        pdf_reader = reader.PdfFileReader(temp_path)
                        pdf_writer = writer.copy_into_new_writer(pdf_reader)

                    # Create signature field
                    field_name = f"Signature_{i+1}_{signer_email.replace('@', '_at_').replace('.', '_')}"

                    # Create signature appearance using TextStampStyle
                    stamp_style = TextStampStyle(
                        stamp_text=(
                            f"Digitally signed by: {signer_name}\n"
                            f"Email: {signer_email}\n"
                            f"Date: {signing_time}\n"
                            f"Certificate: Self-signed"
                        ),
                        background_opacity=0.1,
                        border_width=1
                    )

                    # Add signature field with larger box for visual signature
                    sig_field = fields.SigFieldSpec(
                        sig_field_name=field_name,
                        on_page=0,  # First page
                        box=(50, 50 + i * 100, 330, 130 + i * 100)  # Larger box for visual signature
                    )
                    fields.append_signature_field(pdf_writer, sig_field)

                    # Create signature metadata with visual appearance
                    sig_meta = signers.PdfSignatureMetadata(
                        field_name=field_name,
                        reason=f"Document signed by {signer_name}",
                        location="Document Signing Platform",
                        name=signer_name,
                        certify=False,
                        subfilter=fields.SigSeedSubFilter.ADOBE_PKCS7_DETACHED,
                        embed_validation_info=False,
                        app_build_props=stamp_style  # Add the visual stamp
                    )

                    # Sign the document
                    signed_output = BytesIO()
                    try:
                        signers.sign_pdf(
                            pdf_writer,
                            sig_meta,
                            signer=signer_cert,
                            output=signed_output
                        )

                        # Write signed content back to temp file
                        with open(temp_path, 'wb') as f:
                            f.write(signed_output.getvalue())

                    except Exception as e:
                        logger.error(f"Error signing PDF with visual stamp: {e}")
                        # Fallback: sign without visual appearance
                        sig_meta_fallback = signers.PdfSignatureMetadata(
                            field_name=field_name,
                            reason=f"Document signed by {signer_name}",
                            location="Document Signing Platform",
                            name=signer_name,
                            certify=False,
                            subfilter=fields.SigSeedSubFilter.ADOBE_PKCS7_DETACHED,
                            embed_validation_info=False
                        )

                        signers.sign_pdf(
                            pdf_writer,
                            sig_meta_fallback,
                            signer=signer_cert,
                            output=signed_output
                        )

                        with open(temp_path, 'wb') as f:
                            f.write(signed_output.getvalue())

                # Read the final signed document
                with open(temp_path, 'rb') as f:
                    signed_pdf_data = f.read()

                # Try to upload to external storage
                if self.ensure_authenticated():
                    try:
                        filename = f"signed_document_{local_document_id}.pdf"
                        success, storage_result = self.storage_client.upload(
                            data=signed_pdf_data,
                            filename=filename,
                            document_id=None
                        )

                        if success:
                            storage_document_id = storage_result
                            uploaded_to_storage = True
                            logger.info(f"Document uploaded to storage with ID: {storage_document_id}")
                        else:
                            logger.warning(f"Failed to upload to storage: {storage_result}")
                    except Exception as e:
                        logger.error(f"Storage upload error: {e}")
                else:
                    logger.info("Storage not authenticated, saving locally only")

                # Always save locally as backup using the custom ID
                local_path = f"signed_documents/{local_document_id}.pdf"
                os.makedirs("signed_documents", exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(signed_pdf_data)
                logger.info(f"Document saved locally: {local_path}")

                # Generate signing URLs for each signer based on their mode
                for i, signer_data in enumerate(signers_data):
                    signer_email = signer_data['signer_email']
                    signer_name = signer_data['signer_name']
                    signer_mode = signer_data.get('mode', 'DIRECT_SIGNING')

                    # Generate signing URL if DIRECT_SIGNING mode
                    signing_url = None
                    if signer_mode == 'DIRECT_SIGNING':
                        # Use the document storage client to get download URL
                        if uploaded_to_storage:
                            signing_url = self.storage_client.get_download_url(storage_document_id)
                        else:
                            # Fallback to local download URL using the custom ID
                            signing_url = f"/api/selfsign/documents/{local_document_id}/download"

                    signing_urls.append({
                        "signer_email": signer_email,
                        "signer_name": signer_name,
                        "signing_url": signing_url,
                        "signed": True,  # Self-signing is immediately completed
                        "signed_at": datetime.now(timezone.utc).isoformat(),
                        "mode": signer_mode,
                        "status": "completed",
                        "has_visual_signature": True
                    })

                return {
                    "document_id": storage_document_id,  # Return the ObjectId for consistency
                    "local_document_id": local_document_id,  # Include custom ID for local reference
                    "status": "completed",
                    "service": "selfsign",
                    "signing_urls": signing_urls,
                    "storage_id": storage_document_id if uploaded_to_storage else None,
                    "local_path": local_path,
                    "uploaded_to_storage": uploaded_to_storage,
                    "metadata": metadata or {}
                }

            finally:
                # Clean up temp file if it still exists
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Error in self-signing: {str(e)}")
            raise Exception(f"Self-signing failed: {str(e)}")


    async def download_document(self, document_id: str):
        """Download signed document by ID"""
        try:
            # Try to find the document locally first
            local_paths = [
                f"signed_documents/{document_id}.pdf",  # Direct ID match
                f"signed_documents/self_{document_id}.pdf"  # With self prefix
            ]

            # Also check for files that contain the document_id
            #import glob
            #pattern_paths = glob.glob(f"signed_documents/*{document_id}*.pdf")
            #local_paths.extend(pattern_paths)

            #for local_path in local_paths:
            #    if os.path.exists(local_path):
            #        from fastapi.responses import FileResponse
            #        return FileResponse(
            #            local_path,
            #            media_type='application/pdf',
            #            filename=f"signed_document_{document_id}.pdf"
            #        )

            # Try to download from storage if not found locally
            logger.info("Download if authenticated")
            if self.ensure_authenticated():
                logger.info("Was authenticated")
                try:
                    download_url = self.storage_client.get_download_url(document_id)
                    if download_url:
                        from fastapi.responses import RedirectResponse
                        return RedirectResponse(url=download_url)
                except Exception as e:
                    logger.error(f"Error getting download URL from storage: {e}")

            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Document not found")

        except Exception as e:
            logger.error(f"Error downloading document {document_id}: {str(e)}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """Get document status for self-signed documents"""
        try:
            # Check if document exists locally
            import glob
            local_files = glob.glob(f"signed_documents/*{document_id}*.pdf")

            if local_files:
                # Document exists locally
                local_file = local_files[0]
                file_stats = os.stat(local_file)

                return {
                    "document_id": document_id,
                    "status": "completed",
                    "service": "selfsign",
                    "created_at": datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    "completed_at": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "file_size": file_stats.st_size,
                    "local_path": local_file,
                    "metadata": {}
                }

            # Check storage if not found locally
            if self.ensure_authenticated():
                try:
                    # Try to get document info from storage
                    download_url = self.storage_client.get_download_url(document_id)
                    if download_url:
                        return {
                            "document_id": document_id,
                            "status": "completed",
                            "service": "selfsign",
                            "storage_url": download_url,
                            "metadata": {}
                        }
                except Exception as e:
                    logger.error(f"Error checking storage for document {document_id}: {e}")

            # Document not found
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Document not found")

        except Exception as e:
            logger.error(f"Error getting status for document {document_id}: {str(e)}")
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

    def get_download_url(self, document_id: str) -> str:
        """Get direct download URL for document"""
        logger.info("--->get_download_url, id=" + document_id)
        # For local storage, we'll need to serve through our API
        local_path = f"signed_documents/{document_id}.pdf"
        if os.path.exists(local_path):
            # Return a URL that points to our download endpoint
            return f"/api/selfsign/documents/{document_id}/download"

        # Try external storage
        if self.ensure_authenticated():
            success, result = self.storage_client.get_download_url(document_id, as_pdf=True)
            if success:
                return result
            else:
                raise Exception(f"Failed to get download URL: {result}")

        raise Exception(f"Document {document_id} not found")

    def validate_document(self, document_id: str) -> Dict[str, Any]:
        """Validate document signatures for DSS compatibility"""
        try:
            # Download document for validation
            document_data = self.download_document(document_id)

            with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
                temp_file.write(document_data)
                temp_file.flush()

                with open(temp_file.name, 'rb') as f:
                    pdf_reader = reader.PdfFileReader(f)

                validation_results = []

                for i, sig in enumerate(pdf_reader.embedded_signatures):
                    try:
                        result = validate_pdf_signature(sig)
                        validation_results.append({
                            "signature_index": i,
                            "signer": str(sig.signer_info.signer_identifier),
                            "intact": result.intact,
                            "valid": result.valid,
                            "trusted": result.trusted,
                            "signing_time": sig.signer_info.signing_time.isoformat() if sig.signer_info.signing_time else None,
                            "dss_compatible": True  # pyHanko creates DSS-compatible signatures
                        })
                    except Exception as e:
                        validation_results.append({
                            "signature_index": i,
                            "error": str(e),
                            "valid": False
                        })

                return {
                    "document_id": document_id,
                    "validation_results": validation_results,
                    "overall_valid": all(r.get("valid", False) for r in validation_results),
                    "dss_compatible": True
                }

        except Exception as e:
            logger.error(f"Error validating document: {str(e)}")
            return {
                "document_id": document_id,
                "error": str(e),
                "valid": False
            }

# Create global instance with configurable storage URL
STORAGE_SERVER_URL = os.getenv('DOCUMENT_STORAGE_URL', 'http://localhost:3001')
STORAGE_LOGIN_URL = os.getenv('DOCUMENT_STORAGE_LOGIN_URL', STORAGE_SERVER_URL)
STORAGE_EMAIL = os.getenv('DOCUMENT_STORAGE_EMAIL')
STORAGE_PASSWORD = os.getenv('DOCUMENT_STORAGE_PASSWORD')
STORAGE_CODE = os.getenv('DOCUMENT_STORAGE_CODE', '')

selfsign = SelfSignService(
    storage_server_url=STORAGE_SERVER_URL,
    login_server_url=STORAGE_LOGIN_URL,
    storage_email=STORAGE_EMAIL,
    storage_password=STORAGE_PASSWORD,
    storage_code=STORAGE_CODE
)
