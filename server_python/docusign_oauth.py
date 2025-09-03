# docusign_oauth.py
import base64, logging, os, requests, time
from urllib.parse import urlencode, parse_qs, urlparse
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DocuSignOAuth:
    def __init__(self):
        self.integration_key = os.getenv('DOCUSIGN_INTEGRATION_KEY', '380ba0c6-5812-4e1f-9066-520c6a19ea93')
        self.secret_key = os.getenv('DOCUSIGN_SECRET_KEY', 'dfbf4e4b-f62b-421c-8391-d5805398e75c')
        self.redirect_uri = os.getenv('DOCUSIGN_REDIRECT_URI', 'http://localhost:8000/auth/docusign/callback')
        self.base_path = os.getenv('DOCUSIGN_BASE_PATH', 'https://demo.docusign.net/restapi')
        self.auth_server = os.getenv('DOCUSIGN_AUTH_SERVER', 'https://account-d.docusign.com')

        # Token storage (in production, use database or secure storage)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None

    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate the authorization URL for OAuth flow

        Args:
            state: Optional state parameter for security

        Returns:
            Authorization URL
        """
        params = {
            'response_type': 'code',
            'scope': 'signature',
            'client_id': self.integration_key,
            'redirect_uri': self.redirect_uri
        }

        if state:
            params['state'] = state

        auth_url = f"{self.auth_server}/oauth/auth?" + urlencode(params)
        logger.info(f"Generated authorization URL: {auth_url}")
        return auth_url

    def exchange_code_for_token(self, authorization_code):
        """
        Exchange authorization code for access token

        Args:
            authorization_code: The authorization code from callback

        Returns:
            Token information dictionary
        """
        try:
            # Prepare authentication header
            auth_string = f"{self.integration_key}:{self.secret_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_bytes}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri
            }

            response = requests.post(
                f"{self.auth_server}/oauth/token",
                headers=headers,
                data=data
            )

            if response.status_code == 200:
                token_data = response.json()

                # Store tokens
                self.access_token = token_data['access_token']
                self.refresh_token = token_data.get('refresh_token')
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = time.time() + expires_in

                logger.info("Successfully obtained access token")
                return token_data
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to exchange code for token: {response.text}")

        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            raise

    def refresh_access_token(self) -> Dict[str, str]:
        """
        Refresh the access token using refresh token

        Returns:
            New token information
        """
        if not self.refresh_token:
            raise Exception("No refresh token available")

        try:
            auth_string = f"{self.integration_key}:{self.secret_key}"
            auth_bytes = base64.b64encode(auth_string.encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_bytes}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token
            }

            response = requests.post(
                f"{self.auth_server}/oauth/token",
                headers=headers,
                data=data
            )

            if response.status_code == 200:
                token_data = response.json()

                # Update stored tokens
                self.access_token = token_data['access_token']
                if 'refresh_token' in token_data:
                    self.refresh_token = token_data['refresh_token']
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = time.time() + expires_in

                logger.info("Successfully refreshed access token")
                return token_data
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                raise Exception(f"Failed to refresh token: {response.text}")

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise

    def get_valid_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary

        Returns:
            Valid access token
        """
        # Check if we have a token and it's not expired
        if self.access_token and self.token_expires_at:
            # Add 5 minute buffer before expiration
            if time.time() < (self.token_expires_at - 300):
                return self.access_token

        # Token is expired or doesn't exist, try to refresh
        if self.refresh_token:
            try:
                self.refresh_access_token()
                return self.access_token
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise Exception("Access token expired and refresh failed. Re-authorization required.")

        raise Exception("No valid access token available. Authorization required.")
