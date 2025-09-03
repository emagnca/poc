# docusign_service.py
import base64, logging, os, jwt, requests, traceback
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# DocuSign Python SDK imports
from docusign_esign import ApiClient, Configuration, CustomFields, EnvelopesApi, ListCustomField, TextCustomField
from docusign_esign.models import (
    Document, Signer, SignHere, Tabs, EnvelopeDefinition,
    Recipients, EnvelopeSummary, RecipientViewRequest, ViewUrl, Envelope
)
from docusign_esign.client.api_exception import ApiException



logger = logging.getLogger(__name__)

class DocuSignService:
    def __init__(self, docusign_oauth):

        self.integration_key = os.getenv('DOCUSIGN_INTEGRATION_KEY', '380ba0c6-5812-4e1f-9066-520c6a19ea93')
        self.user_id = os.getenv('DOCUSIGN_USER_ID', '71153734-82ad-44d3-9a17-db4c7dfe5025')
        self.account_id = os.getenv('DOCUSIGN_ACCOUNT_ID', '21638d02-1341-4dbd-befc-bb9800e7e7cb')
        self.base_path = os.getenv('DOCUSIGN_BASE_PATH', 'https://demo.docusign.net/restapi')
        self.auth_server = os.getenv('DOCUSIGN_AUTH_SERVER', 'account-d.docusign.com')
        self.secret_key = os.getenv('DOCUSIGN_SECRET_KEY', 'dfbf4e4b-f62b-421c-8391-d5805398e75c')

        self.oauth = docusign_oauth

        self.access_token = None
        self.token_expires_at = None

        # Private key file path
        self.private_key_path = "keys/private_key.txt"

    def initiate_signing_process(self, document_content, signers, metadata):
        """
        Initiate document signing process with multiple signers

        Args:
            document_content: PDF document as bytes
            signers: List of signer dictionaries with email, name, and mode
            metadata: tags

        Returns:
            Dict with envelope_id and signing URLs
        """
        try:
            logger.info("Initating api client")
            # Setup API client
            api_client = self._get_api_client()

            logger.info("Creating document")
            # Create document
            document = Document(
                document_base64=base64.b64encode(document_content).decode('utf-8'),
                name="Document to Sign",
                file_extension="pdf",
                document_id="1"
            )

            # Create signers
            envelope_signers = []
            signing_urls = []

            logger.info("Creating signers")

            for i, signer_info in enumerate(signers, 1):
                logger.info(signer_info)
                signer_email = signer_info.signer_email
                logger.info("email:" + signer_email)
                signer_name = signer_info.signer_name
                mode = signer_info.mode
                recipient_id = str(i)

                logger.info("Creating Signer:" + signer_name)
                # Create signer
                signer = Signer(
                    email=signer_email,
                    name=signer_name,
                    recipient_id=recipient_id
                )
                logger.info("Signer created")

                # Add signature tab
                sign_here = SignHere(
                    document_id="1",
                    page_number="1",
                    recipient_id=recipient_id,
                    tab_label=f"SignHereTab{i}",
                    x_position="100",
                    y_position=str(100 + (i-1) * 50)  # Offset for multiple signers
                )

                tabs = Tabs(sign_here_tabs=[sign_here])
                signer.tabs = tabs
                envelope_signers.append(signer)

            text_custom_fields = []
            list_custom_fields = []

            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, list):
                        # For dropdown/list values
                        list_field = ListCustomField(
                            name=key,
                            value=value[0] if value else "",
                            list_items=value,
                            show="true",
                            required="false"
                        )
                        list_custom_fields.append(list_field)
                    else:
                        # For text values
                        text_field = TextCustomField(
                            name=key,
                            value=str(value),
                            show="true",
                            required="false"
                        )
                        text_custom_fields.append(text_field)

            # Create envelope definition
            envelope_definition = EnvelopeDefinition(
                email_subject="Please sign this document",
                documents=[document],
                recipients=Recipients(signers=envelope_signers),
                custom_fields=CustomFields(
                    text_custom_fields=text_custom_fields,
                    list_custom_fields=list_custom_fields
                ) if (text_custom_fields or list_custom_fields) else None,
                status="sent"
            )

            logger.info("Creating envelope")
            # Create envelope
            envelopes_api = EnvelopesApi(api_client)
            envelope_summary = envelopes_api.create_envelope(
                self.account_id,
                envelope_definition=envelope_definition
            )

            envelope_id = envelope_summary.envelope_id

            logger.info("Evenlope create with id:" + envelope_id)

            # Handle different signing modes for each signer
            for i, signer_info in enumerate(signers, 1):
                mode = signer_info.mode
                recipient_id = str(i)

                if mode == 'EMAIL_NOTIFICATION':
                    # For email mode, we'll send the envelope after all signers are processed
                    logger.info("Appending url")
                    signing_urls.append({
                        "signer_email": signer_info.signer_email,
                        "signer_name": signer_info.signer_name,
                        "signing_url": None,  # No direct URL for email mode
                        "mode": mode
                    })
                    logger.info("Url appended")
                else:  # DIRECT_SIGNING mode
                    # Create recipient view for embedded signing
                    view_request = RecipientViewRequest(
                        return_url="https://your-app.com/signing-complete",
                        authentication_method="none",
                        email=signer_info.signer_email,
                        user_name=signer_info.signer_name,
                        recipient_id=recipient_id
                    )

                    logger.info("Creating view")
                    recipient_view = envelopes_api.create_recipient_view(
                        self.account_id,
                        envelope_id=envelope_id,
                        recipient_view_request=view_request
                    )
                    logger.info("View created with url: " + recipient_view.url)

                    signing_urls.append({
                        "signer_email": signer_info.signer_email,
                        "signer_name": signer_info.signer_name,
                        "signing_url": recipient_view.url,
                        "mode": mode
                    })

            logger.info("Finished init process for Docusign")

            return {
                "document_id": envelope_id,
                "signing_urls": signing_urls,
                "service": "docusign"
            }

        except ApiException as e:
            logger.error(f"DocuSign API error: {e}")
            print(traceback.format_exc())
            raise Exception(f"Failed to create DocuSign envelope: {e}")
        except Exception as e:
            logger.error(f"Error initiating DocuSign signing process: {e}")
            raise

    def get_signing_status(self, envelope_id: str) -> Dict[str, Any]:
        """
        Get the signing status of an envelope

        Args:
            envelope_id: The DocuSign envelope ID

        Returns:
            Dict with status information
        """
        try:
            logger.info("Get status!!!!!!!!!!!!!!!!!!!!")
            api_client = self._get_api_client()

            logger.info("Getting the api client")
            envelopes_api = EnvelopesApi(api_client)

            logger.info("Checking envelopes api")
            # Get envelope information
            envelope = envelopes_api.get_envelope(self.account_id, envelope_id)

            logger.info("Got envelope:" + str(envelope))

            # Get recipients information for detailed status
            recipients = envelopes_api.list_recipients(self.account_id, envelope_id)

            logger.info("Got Recepients:" + str(recipients))

            # Process signer information
            signers_status = []
            for signer in recipients.signers or []:
                logger.info("signer:" + str(signer.email))
                signers_status.append({
                    "email": signer.email,
                    "name": signer.name,
                    "signed": signer.status == "completed",
                    "signed_at": signer.signed_date_time,
                    "status": signer.status
                })

            return {
                "document_id": envelope_id,
                "status": envelope.status,
                "signed": envelope.status == "completed",
                "service": "docusign",
                "signers": signers_status
            }

        except ApiException as e:
            logger.error(f"Error getting DocuSign envelope status: {e}")
            raise Exception(f"Failed to get envelope status: {e}")

    def get_signed_document(self, envelope_id: str) -> bytes:
        try:
            # Debug: Log the envelope ID
            logger.info(f"Attempting to download document for envelope: {envelope_id}")
            logger.info(f"Envelope ID length: {len(envelope_id)}")
            logger.info(f"Envelope ID format valid: {len(envelope_id) == 36 and envelope_id.count('-') == 4}")

            api_client = self._get_api_client()
            envelopes_api = EnvelopesApi(api_client)

            # First check if envelope exists
            envelope = envelopes_api.get_envelope(self.account_id, envelope_id)
            logger.info(f"Envelope status: {envelope.status}")

            # Only download if envelope is completed
            if envelope.status != "completed":
                raise Exception(f"Cannot download document. Envelope status is: {envelope.status}")

            logger.info(f"Account ID: {self.account_id}")
            logger.info(f"Envelope ID for download: '{envelope_id}'")
            logger.info(f"Document ID: 'combined'")

            # Method 1: Get documents list first, then download specific document
            documents = envelopes_api.list_documents(self.account_id, envelope_id)
            logger.info(f"Available documents: {[doc.document_id for doc in documents.envelope_documents]}")

            document_bytes = envelopes_api.get_document(
                self.account_id,
                "combined",
                envelope_id
            )

            return document_bytes

        except ApiException as e:
            logger.error(f"DocuSign API error: {e}")
            logger.error(f"Response body: {e.body if hasattr(e, 'body') else 'No body'}")

            raise Exception(f"Failed to download signed document: {e}")


    async def search_documents(self, search_params, limit, offset):
        """Search DocuSign envelopes"""
        try:
            api_client = self._get_api_client()
            envelopes_api = EnvelopesApi(api_client)

            # Build parameters directly (no options class needed)
            from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            # Build parameters - only include status if it has a value
            params = {
                'count': str(min(limit, 100)),
                'start_position': str(offset),
                'from_date': from_date
            }

            # Only add status if provided and not None
            if search_params.get('status'):
                status_mapping = {
                    'pending': 'sent',
                    'sent': 'sent',
                    'completed': 'completed',
                    'signed': 'completed'
                }
                mapped_status = status_mapping.get(search_params['status'].lower(), search_params['status'])
                params['status'] = mapped_status

            # Call with unpacked parameters
            envelopes_result = envelopes_api.list_status_changes(
                self.account_id,
                **params
            )


            results = []

            # Process envelopes
            for envelope in envelopes_result.envelopes or []:
                # Get detailed envelope info including custom fields
                envelope_details = envelopes_api.get_envelope(
                    self.account_id,
                    envelope.envelope_id,
                    include="custom_fields"
                )

                document_info = {
                    'document_id': envelope.envelope_id,
                    'title': envelope.email_subject or 'Untitled',
                    'status': envelope.status,
                    'created_at': envelope.created_date_time,
                    'modified_at': envelope.status_changed_date_time,
                    'service': 'docusign',
                    'metadata': {}
                }

                # Extract custom fields as metadata
                if envelope_details.custom_fields:
                    if envelope_details.custom_fields.text_custom_fields:
                        for field in envelope_details.custom_fields.text_custom_fields:
                            document_info['metadata'][field.name] = field.value

                # Filter by metadata
                matches = True
                for param_key, param_value in search_params.items():
                    if param_key == 'status':
                        continue
                    elif param_key == 'title':
                        if param_value.lower() not in document_info['title'].lower():
                            matches = False
                            break
                    else:
                        doc_value = document_info['metadata'].get(param_key, '').lower()
                        if param_value.lower() not in doc_value:
                            matches = False
                            break

                if matches:
                    results.append(document_info)

            return results

        except Exception as e:
            logger.error(f"DocuSign search error: {e}")
            print(traceback.format_exc())
            raise Exception(f"Failed to search DocuSign documents: {e}")



    def _get_access_token(self):
        # Force UTC and add debugging
        utc_now = datetime.utcnow()
        current_time = int(utc_now.timestamp())

        # Log the actual datetime for debugging
        logger.info(f"Current UTC datetime: {utc_now}")
        logger.info(f"Current timestamp: {current_time}")

        # Use current time minus 5 minutes for clock skew
        issued_at = current_time - 300 + 7200
        expiry_time = current_time + 3600 + 7200

        payload = {
            "iss": self.integration_key,
            "sub": self.user_id,
            "aud": "account-d.docusign.com",
            "iat": issued_at,
            "exp": expiry_time,
            "scope": "signature impersonation"
        }

        # Convert timestamps back to readable dates for verification
        logger.info(f"JWT issued at: {datetime.fromtimestamp(issued_at)} UTC")
        logger.info(f"JWT expires at: {datetime.fromtimestamp(expiry_time)} UTC")


        try:
            private_key = self._load_private_key()

            # Debug: Print the JWT payload
            logger.info(f"JWT payload: {payload}")
            logger.info(f"Integration Key: {self.integration_key}")
            logger.info(f"User ID: {self.user_id}")
            logger.info(f"Auth Server: {self.auth_server}")

            jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
            logger.info(f"Generated JWT token (first 50 chars): {jwt_token[:50]}...")

            url = f"https://{self.auth_server}/oauth/token"
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }

            logger.info(f"Making request to: {url}")
            response = requests.post(url, data=data, headers=headers)

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response body: {response.text}")

            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.token_expires_at = current_time + token_data.get('expires_in', 3600)
                logger.info("Successfully obtained DocuSign access token")
                return self.access_token
            else:
                raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            raise



    def _load_private_key(self):
        """Load the RSA private key from keys/private_key.txt"""
        try:
            if not os.path.exists(self.private_key_path):
                raise FileNotFoundError(f"Private key file not found: {self.private_key_path}")

            with open(self.private_key_path, 'r') as key_file:
                private_key_content = key_file.read().strip()

            # Validate that it looks like a private key
            if not private_key_content.startswith('-----BEGIN'):
                raise ValueError("Invalid private key format. Expected PEM format starting with -----BEGIN")

            logger.info(f"Successfully loaded private key from {self.private_key_path}")
            return private_key_content

        except Exception as e:
            logger.error(f"Error loading private key: {e}")
            raise Exception(f"Failed to load private key from {self.private_key_path}: {e}")


    def _get_api_client(self):
        """Setup and return configured API client"""
        api_client = ApiClient()
        api_client.host = self.base_path
        if not self.access_token:
            self.access_token = self._get_access_token()

        api_client.set_default_header("Authorization", f"Bearer {self.access_token}")

        return api_client

    def _get_access_token_oauth(self):
        """
        Get OAuth access token
        """
        return self.oauth.get_valid_access_token()


# Usage example
if __name__ == "__main__":
    docusign_oauth = DocuSignOAuth()
    service = DocuSignService(docusign_oauth)

    # Example usage
    with open("document.pdf", "rb") as f:
        document_content = f.read()

    signers = [
        {
            "signer_email": "magnus.carlhammar@yahoo.se",
            "signer_name": "Magnus",
            "mode": "DIRECT_SIGNING"
        }
    ]

    # Initiate signing
    result = service.initiate_signing_process(document_content, signers)
    print(f"Envelope created: {result['document_id']}")

    # Check status
    status = service.get_signing_status(result['document_id'])
    print(f"Status: {status['status']}")

    # Download when complete
    if status['signed']:
        signed_doc = service.get_signed_document(result['document_id'])
        with open("signed_document.pdf", "wb") as f:
            f.write(signed_doc)
