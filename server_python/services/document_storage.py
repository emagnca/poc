# services/document_storage.py
import requests
import mimetypes
import os
import tempfile
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class DocumentStorageClient:
    """Client for external document storage service with authentication"""

    def __init__(self, server_url: str, login_server_url: str = None):
        self.server = server_url.rstrip('/')
        self.login_server = login_server_url.rstrip('/') if login_server_url else self.server
        self.access_token = None
        self.refresh_token = None
        self.company = None

    def login_usrpwd(self, email: str="x", password: str="x", code: str = "121212") -> bool:
        """Login using email, password and optional code"""
        logger.info(f"Calling: {self.login_server}/login")
        try:
            response = requests.post(
                f"{self.login_server}/login",
                json={
                    "email": "ehsmaga@yahoo.se",
                    "password": "mySecret",
                    "code": "121212",
                    "type": "password"
                }
            )
            return self._login(response)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False

    def _login(self, response: requests.Response) -> bool:
        """Process login response and store tokens"""
        if response.status_code == 200:
            try:
                j = response.json()
                self.access_token = j['tokens']['access_token']
                self.refresh_token = j['tokens']['refresh_token']

                logger.info(f"AccessToken: {self.access_token}")
                logger.info(f"RefreshToken: {self.refresh_token}")

                if 'company' in j:
                    self.company = j['company']

                return True
            except KeyError as e:
                logger.error(f"Missing key in login response: {e}")
                return False
        else:
            logger.error(f"Login failed: {response.text}")
            return False

    def _refresh(self):
        """Refresh access token using refresh token"""
        response = requests.post(
            f"{self.login_server}/refresh",
            headers={'Authorization': 'Bearer ' + self.refresh_token}
        )
        if response.status_code == 200:
            j = response.json()
            self.access_token = j['tokens']['access_token']
            self.refresh_token = j['tokens']['refresh_token']
            logger.info("Tokens refreshed successfully")
        else:
            logger.error(f"Could not refresh {response.status_code}")

    def _send_get(self, url: str, resend: bool = True) -> requests.Response:
        """Send authenticated GET request with automatic token refresh"""
        response = requests.get(url, headers={'Authorization': 'Bearer ' + self.access_token})
        if response.status_code == 401 and resend:
            self._refresh()
            return self._send_get(url, False)
        else:
            return response

    def _send_post(self, url: str, data: dict = None, resend: bool = True) -> requests.Response:
        """Send authenticated POST request with automatic token refresh"""
        if data is None:
            data = {}
        response = requests.post(url, json=data,
                                 headers={'Authorization': 'Bearer ' + self.access_token})
        if response.status_code == 401 and resend:
            self._refresh()
            return self._send_post(url, data, False)
        else:
            return response

    def upload(self, data: bytes, filename: str, document_id: Optional[str] = None) -> Tuple[bool, str]:
        """Upload document to external storage"""
        if not self.access_token:
            return False, "Not authenticated. Please login first."

        data1 = {}
        data1['metadata'] = '{"title":"' + filename + '","date":"2025-09-03"}'
        data1['filename'] = filename
        data1['mimetype'] = 'application/pdf'
        data1['doctype'] = "Document"
        try:
            url = f"{self.server}/document"
            if document_id:
                url += f'/{document_id}'

            # Get upload URL and fields
            response = self._send_post(url, data=data1)
            if not response.ok:
                return False, f"Failed to get upload URL: {response.text}"

            response_data = response.json()
            if 'url' not in response_data:
                return False, str(response_data)

            upload_url = response_data['url']
            fields = response_data['fields']
            doc_id = response_data['id']

            # Determine mimetype
            mimetype = mimetypes.guess_type(filename)[0]
            if not mimetype:
                mimetype = 'application/pdf'  # Default for PDF documents

            # Upload file (this might not need authentication if using presigned URL)
            files = {
                'file': (filename, data, mimetype),
            }

            upload_response = requests.post(upload_url, files=files, data=fields)
            if not upload_response.ok:
                return False, f'Failed upload to storage. Reason: {upload_response.reason}. Text: {upload_response.text}'

            return True, doc_id

        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            return False, str(e)

    def download(self, document_id: str, as_pdf: bool = True) -> Tuple[bool, bytes]:
        """Download document from external storage"""
        if not self.access_token:
            return False, "Not authenticated. Please login first."

        try:
            url = f"{self.server}/document/{document_id}?isAttachment=true"
            if as_pdf:
                url += '&pdf=true'

            # Get download URL
            response = self._send_get(url)
            if not response.ok:
                return False, f'Get document failed. Reason: {response.reason}. Text: {response.text}'

            download_url = response.json()['url']

            # Download the actual file (might not need authentication if using presigned URL)
            download_response = requests.get(download_url)
            if not download_response.ok:
                return False, f'Download failed. Status: {download_response.status_code}'

            return True, download_response.content

        except Exception as e:
            logger.error(f"Error downloading document: {str(e)}")
            return False, str(e)

    def get_download_url(self, document_id: str, as_pdf: bool = True) -> Tuple[bool, str]:
        """Get direct download URL for document"""
        if not self.access_token:
            return False, "Not authenticated. Please login first."

        try:
            url = f"{self.server}/document/{document_id}?isAttachment=true"
            if as_pdf:
                url += '&pdf=true'

            response = self._send_get(url)
            if not response.ok:
                return False, f'Get document URL failed. Reason: {response.reason}'

            download_url = response.json()['url']
            return True, download_url

        except Exception as e:
            logger.error(f"Error getting download URL: {str(e)}")
            return False, str(e)

    def is_authenticated(self) -> bool:
        """Check if client is authenticated"""
        return self.access_token is not None
