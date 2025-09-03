import cmd2, getpass, json, os, requests, webbrowser

# Single signer
# python client.py sign document.pdf --signer signe.tester@folksam.se "Signe Tester" DIRECT_SIGNING
#
# Multiple signers
# python client.py sign document.pdf
#     --signer signe.tester@folksam.se "Signe Tester" DIRECT_SIGNING \
#     --signer another.tester@folksam.se "Another Tester" EMAIL_NOTIFICATION

class DocumentSigningClient(cmd2.Cmd):
    """CLI client for document signing API with multiple service providers"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = "http://localhost:8000"
        self.session = requests.Session()
        self.current_service = "scrive"  # Default service
        self.last_document_id = None
        self.last_signing_url = None
        self.token = None
        self.authenticated = False

        # Set up command categories
        self.intro = "Document Signing CLI - Type 'help' for available commands"

    def _update_auth_headers(self):
        """Update session headers with authentication token"""
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            self.session.headers.pop("Authorization", None)

    def _check_auth(self):
        """Check if user is authenticated for protected commands"""
        if not self.authenticated:
            self.poutput("❌ Authentication required. Please login first using 'login' command.")
            return False
        return True

    # Authentication commands
    def do_login(self, args):
        """Login with username and password"""
        self.poutput("🔐 Login to Document Signing Platform")
        self.poutput("-" * 40)

        # Get credentials from user
        email = input("Email: ").strip()
        if not email:
            self.poutput("❌ Username cannot be empty")
            return

        # Use getpass for secure password input (doesn't echo to terminal)
        password = getpass.getpass("Password: ")
        if not password:
            self.poutput("❌ Password cannot be empty")
            return

        try:
            # Prepare login data
            login_data = {
                "email": email,
                "password": password
            }

            # Make login request
            response = self.session.post(
                f"{self.base_url}/api/auth/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data["access_token"]
                self.authenticated = True
                self._update_auth_headers()

                self.poutput("✅ Login successful!")
                self.poutput(f"Token type: {token_data.get('token_type', 'bearer')}")
                self.poutput("\n🎉 You can now use authenticated commands")
            else:
                error_data = response.json() if response.headers.get('content-type') == 'application/json' else {}
                error_msg = error_data.get('detail', f'HTTP {response.status_code}')
                self.poutput(f"❌ Login failed: {error_msg}")

        except requests.exceptions.ConnectionError:
            self.poutput(f"❌ Cannot connect to server at {self.base_url}")
        except requests.exceptions.RequestException as e:
            self.poutput(f"❌ Request error: {e}")
        except json.JSONDecodeError:
            self.poutput("❌ Invalid response from server")
        except Exception as e:
            self.poutput(f"❌ Unexpected error: {e}")

    def do_logout(self, args):
        """Logout and clear authentication"""
        self.token = None
        self.authenticated = False
        self._update_auth_headers()
        self.poutput("✅ Logged out successfully")

    def do_auth_status(self, args):
        """Check authentication status"""
        if self.authenticated:
            self.poutput("✅ Authenticated")
        else:
            self.poutput("❌ Not authenticated - use 'login' command")


    # Service management commands
    def do_set_service(self, args):
        """Set the current signing service (scrive or docusign)"""
        if not args:
            self.poutput(f"Current service: {self.current_service}")
            self.poutput("Available services: scrive, docusign")
            return

        service = args.strip().lower()
        if service in ['scrive', 'docusign']:
            self.current_service = service
            self.poutput(f"Service set to: {self.current_service}")
        else:
            self.poutput("Error: Invalid service. Use 'scrive' or 'docusign'")

    def do_services(self, args):
        """List supported services from the server"""
        try:
            url = f"{self.base_url}/api/services"
            response = self.session.get(url)

            if response.status_code == 200:
                data = response.json()
                self.poutput("Supported services:")
                for service in data['supported_services']:
                    marker = " (current)" if service == self.current_service else ""
                    self.poutput(f"  - {service}{marker}")
            else:
                self.poutput(f"Error getting services: {response.status_code}")

        except Exception as e:
            self.poutput(f"Error: {e}")

    # Document signing commands
    sign_parser = cmd2.Cmd2ArgumentParser()
    sign_parser.add_argument('document_path', help='Path to PDF document')
    sign_parser.add_argument('--signer', action='append', nargs=3,
                             metavar=('EMAIL', 'NAME', 'MODE'),
                             help='Add a signer: email name mode (can be used multiple times)')
    sign_parser.add_argument('--service', help='Override current service for this request')
    sign_parser.add_argument('--metadata', action='append', nargs=2,
                             metavar=('KEY', 'VALUE'),
                             help='Add metadata: key value (can be used multiple times)')
    sign_parser.add_argument('--title', help='Document title (shortcut for metadata)')


    @cmd2.with_argparser(sign_parser)
    def do_sign(self, args):
        """Initiate document signing process with multiple signers and optional metadata"""
        service = args.service if args.service else self.current_service

        if not args.signer:
            self.poutput("❌ Error: At least one signer is required")
            self.poutput("Usage: sign document.pdf --signer john@example.com 'John Doe' DIRECT_SIGNING")
            return

        try:
            # Build signers list
            signers = []
            for signer_info in args.signer:
                email, name, mode = signer_info
                signers.append({
                    "signer_email": email,
                    "signer_name": name,
                    "mode": mode
                })

            # Build metadata dictionary
            metadata = {}
            if args.metadata:
                for key, value in args.metadata:
                    metadata[key] = value

            # Add title as metadata if provided
            if args.title:
                metadata['title'] = args.title

            print("Metadata:" + str(metadata))

            url = f"{self.base_url}/api/{service}/sign"

            # Read file content first
            with open(args.document_path, 'rb') as f:
                file_content = f.read()

            # Prepare form data with proper multipart structure
            files = {
                'document': (args.document_path, file_content, 'application/pdf')
            }
            data = {
                'signers': json.dumps(signers)
            }

            # Add metadata if provided
            if metadata:
                data['metadata'] = json.dumps(metadata)

            response = self.session.post(url, files=files, data=data)

            if response.status_code == 200:
                result = response.json()
                self.last_document_id = result['document_id']

                self.poutput(f"✅ Document signing initiated with {service}")
                self.poutput(f"📄 Document ID: {result['document_id']}")

                # Show metadata if provided
                if metadata:
                    self.poutput(f"🏷️  Metadata: {metadata}")

                self.poutput(f"👥 Signers ({len(result['signing_urls'])}):")

                for i, signer_info in enumerate(result['signing_urls']):
                    self.poutput(f"  {i+1}. {signer_info['signer_email']} ({signer_info.get('signing_url', 'Email notification')})")
                    if signer_info.get('signing_url'):
                        self.last_signing_url = signer_info['signing_url']
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                self.poutput(f"❌ Error: {response.status_code}")
                self.poutput(f"Details: {error_data}")

        except FileNotFoundError:
            self.poutput(f"❌ Error: File not found: {args.document_path}")
        except Exception as e:
            self.poutput(f"❌ Error: {e}")


    # Document status commands
    status_parser = cmd2.Cmd2ArgumentParser()
    status_parser.add_argument('document_id', nargs='?', help='Document ID (uses last document if not provided)')
    status_parser.add_argument('--service', help='Override current service for this request')

    @cmd2.with_argparser(status_parser)
    def do_status(self, args):
        """Get document status"""
        document_id = args.document_id if args.document_id else self.last_document_id
        service = args.service if args.service else self.current_service

        if not document_id:
            self.poutput("❌ Error: No document ID provided and no previous document available")
            return

        try:
            url = f"{self.base_url}/api/{service}/documents/{document_id}/status"
            response = self.session.get(url)

            if response.status_code == 200:
                status = response.json()
                self.poutput(f"📄 Document ID: {status['document_id']}")
                self.poutput(f"🔧 Service: {status['service']}")
                self.poutput(f"📊 Status: {status['status']}")
                self.poutput(f"✍️  Signed: {'Yes' if status['signed'] else 'No'}")

                # Display signer information if available
                if status.get('signers'):
                    self.poutput("👥 Signers:")
                    for i, signer in enumerate(status['signers']):
                        signed_status = "✅ Signed" if signer.get('signed') else "⏳ Pending"
                        self.poutput(f"  {i+1}. {signer.get('name', 'Unknown')} ({signer.get('email', 'Unknown')})")
                        self.poutput(f"     Status: {signed_status}")
                        if signer.get('signed_at'):
                            self.poutput(f"     Signed at: {signer['signed_at']}")

            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                self.poutput(f"❌ Error: {response.status_code}")
                self.poutput(f"Details: {error_data}")

        except Exception as e:
            self.poutput(f"❌ Error: {e}")

    # Download commands
    download_parser = cmd2.Cmd2ArgumentParser()
    download_parser.add_argument('document_id', nargs='?', help='Document ID (uses last document if not provided)')
    download_parser.add_argument('--output', '-o', help='Output file path')
    download_parser.add_argument('--service', help='Override current service for this request')

    @cmd2.with_argparser(download_parser)
    def do_download(self, args):
        """Download signed document"""
        document_id = args.document_id if args.document_id else self.last_document_id
        service = args.service if args.service else self.current_service

        if not document_id:
            self.poutput("❌ Error: No document ID provided and no previous document available")
            return

        try:
            url = f"{self.base_url}/api/{service}/documents/{document_id}/download"
            response = self.session.get(url)

            if response.status_code == 200:
                output_path = args.output or f"downloads/signed_document_{document_id}.pdf"
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                self.poutput(f"✅ Document downloaded: {output_path}")
                webbrowser.open('file://' + os.path.realpath(output_path))
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                self.poutput(f"❌ Error: {response.status_code}")
                self.poutput(f"Details: {error_data}")

        except Exception as e:
            self.poutput(f"❌ Error: {e}")

    def do_open(self, args):
        """Open the last signing URL in browser"""
        if not self.last_signing_url:
            self.poutput("❌ Error: No signing URL available. Create a document first.")
            return

        self.poutput(f"🌐 Opening: {self.last_signing_url}")
        webbrowser.open(self.last_signing_url)

    # Document search commands
    search_parser = cmd2.Cmd2ArgumentParser()
    search_parser.add_argument('--handler', help='Filter by handler')
    search_parser.add_argument('--system', help='Filter by system')
    search_parser.add_argument('--status', help='Filter by document status')
    search_parser.add_argument('--title', help='Filter by document title')
    search_parser.add_argument('--service', help='Override current service for this request')
    search_parser.add_argument('--limit', type=int, default=50, help='Maximum number of results (default: 50)')
    search_parser.add_argument('--offset', type=int, default=0, help='Offset for pagination (default: 0)')

    @cmd2.with_argparser(search_parser)
    def do_search(self, args):
        """Search documents based on metadata"""
        service = args.service if args.service else self.current_service

        try:
            # Build query parameters
            params = {}
            if args.handler:
                params['handler'] = args.handler
            if args.service:
                params['service'] = args.service
            if args.system:
                params['system'] = args.system
            if args.status:
                params['status'] = args.status
            if args.title:
                params['title'] = args.title
            if args.limit:
                params['limit'] = args.limit
            if args.offset:
                params['offset'] = args.offset

            if not params:
                self.poutput("❌ Error: At least one search parameter is required")
                self.poutput("Use --help to see available search options")
                return

            url = f"{self.base_url}/api/signatures/search"
            response = self.session.get(url, params=params)

            if response.status_code == 200:
                result = response.json()
                results = result['results']
                search_params = result['search_params']

                self.poutput(f"🔍 Search Results ({len(results)} found)")
                self.poutput(f"🔧 Service: {service}")

                # Show search parameters
                if search_params:
                    self.poutput("📋 Search Parameters:")
                    for key, value in search_params.items():
                        self.poutput(f"  {key}: {value}")

                if not results:
                    self.poutput("📄 No documents found matching the criteria")
                    return

                # Display results
                self.poutput(f"\n📄 Documents:")
                for i, doc in enumerate(results, 1):
                    self.poutput(f"\n{i}. {doc['title']} (ID: {doc['document_id']})")
                    self.poutput(f"   Status: {doc['status']}")
                    self.poutput(f"   Created: {doc.get('created_at', 'Unknown')}")

                    # Show metadata
                    if doc.get('metadata'):
                        self.poutput("   Metadata:")
                        for key, value in doc['metadata'].items():
                            if key != 'title':  # Don't duplicate title
                                self.poutput(f"     {key}: {value}")

                # Show pagination info
                if result.get('limit') or result.get('offset'):
                    self.poutput(f"\n📊 Showing results {result.get('offset', 0) + 1}-{result.get('offset', 0) + len(results)}")
                    if len(results) == result.get('limit', 50):
                        self.poutput("   Use --offset to see more results")

            elif response.status_code == 501:
                self.poutput(f"❌ Search not implemented for {service} service yet")
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                self.poutput(f"❌ Error: {response.status_code}")
                self.poutput(f"Details: {error_data}")

        except Exception as e:
            self.poutput(f"❌ Error: {e}")

    def do_find(self, args):
        """Quick search by document title or ID"""
        if not args:
            self.poutput("❌ Error: Please provide a search term")
            self.poutput("Usage: find <title_or_id>")
            return

        search_term = args.strip()

        # Try to search by title first
        try:
            url = f"{self.base_url}/api/signatures/search"
            params = {'title': search_term, 'limit': 10}
            response = self.session.get(url, params=params)

            if response.status_code == 200:
                result = response.json()
                results = result['results']

                if results:
                    self.poutput(f"🔍 Found {len(results)} document(s) matching '{search_term}':")
                    for i, doc in enumerate(results, 1):
                        self.poutput(f"{i}. {doc['title']} (ID: {doc['document_id']}) - {doc['status']}")
                else:
                    self.poutput(f"📄 No documents found matching '{search_term}'")
            else:
                self.poutput(f"❌ Search failed: {response.status_code}")

        except Exception as e:
            self.poutput(f"❌ Error: {e}")

    def do_health(self, args):
        """Check API health"""
        try:
            url = f"{self.base_url}/api/health"
            response = self.session.get(url)

            if response.status_code == 200:
                health = response.json()
                self.poutput(f"✅ API Status: {health['status']}")
                self.poutput(f"🔧 Service: {health['service']}")
            else:
                self.poutput(f"❌ API Health Check Failed: {response.status_code}")

        except Exception as e:
            self.poutput(f"❌ Error: {e}")

    def do_info(self, args):
        """Show current session information"""
        self.poutput("📋 Current Session Info:")
        self.poutput(f"🔧 Service: {self.current_service}")
        self.poutput(f"🌐 Server: {self.base_url}")
        self.poutput(f"📄 Last Document ID: {self.last_document_id or 'None'}")
        self.poutput(f"🔗 Last Signing URL: {self.last_signing_url or 'None'}")


if __name__ == '__main__':
    import sys

    # Create and run the CLI
    app = DocumentSigningClient(persistent_history_file="~/.document_signing_history")

    # If arguments provided, run single command
    if len(sys.argv) > 1:
        app.onecmd_plus_hooks(' '.join(sys.argv[1:]))
    else:
        app.cmdloop()
