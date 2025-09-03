import base64, json, logging, pprint, requests
from models import SigningMode

BASE_URL='https://api-testbed.scrive.com'
FILE_PATH='C:/Users/kmca04/tmp/dummy.pdf'
LOGIN_EMAIL='magnuscarlhammar@yahoo.se'
LOGIN_PASSWORD='SigneTester12'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

auth_headers = None
id = None

def login(email=LOGIN_EMAIL, password=LOGIN_PASSWORD):
    print("login")
    if auth_headers:
        return auth_headers

    rsp = requests.post(BASE_URL + "/api/v2/getpersonaltoken", data={"email":email, "password":password})

    if rsp.status_code != 200:
        raise Exception('Failed to login')
    else:
        j = rsp.json()
        header = 'oauth_signature_method="PLAINTEXT", '
        header += 'oauth_consumer_key="' + j['apitoken'] + '", '
        header += 'oauth_token="' + j['accesstoken'] + '", '
        header += 'oauth_signature="' + j['apisecret'] + '&' + j['accesssecret'] + '"'
        return {'Authorization': header}

def create_author_party():
    """Create the author party using LOGIN_EMAIL"""
    party = {
        "signatory_role": "viewer",
        "is_author": True,
        "is_signatory": False,
        "sign_order": 1,
        "delivery_method": "email",
        "authentication_method_to_sign": "standard",
        "authentication_method_to_view": "standard",
        "authentication_method_to_view_archived": "standard",
        "confirmation_delivery_method": "email",
        "notification_delivery_method": "email",
        "fields": [
            {
                "type": "email",
                "value": LOGIN_EMAIL
            },
            {
                "type": "full_name",
                "value": "Document Author"  # You can customize this name
            }
        ]
    }
    return party

def create_signer_party(email, name, sign_order=2, delivery_method="api"):
    """Create a signer party (now starts from sign_order=2)"""
    party = {
        "signatory_role": "signing_party",
        "is_author": False,
        "is_signatory": True,
        "sign_order": sign_order,
        "delivery_method": "api" if delivery_method == SigningMode.DIRECT_SIGNING else "email",
        "authentication_method_to_sign": "standard",
        "authentication_method_to_view": "standard",
        "authentication_method_to_view_archived": "standard",
        "confirmation_delivery_method": "email",
        "notification_delivery_method": "none" if delivery_method == "api" else "email",
        "fields": [
            {
                "type": "email",
                "value": email
            },
            {
                "type": "full_name",
                "value": name
            }
        ]
    }
    return party

def new_request(file_content_bytes, auth_headers):
    print("new_request")
    file_data = base64.b64encode(file_content_bytes)
    data = {"file": file_data}

    rsp = requests.post(BASE_URL + '/api/v2/documents/new',
                        data=data,
                        headers=auth_headers)
    j = rsp.json()
    id = j['id']
    if not id:
        raise Exception('Failed to create new document')
    return id

def update_with_signers(id, signers, auth_headers, metadata=None):
    print("update_with_signers")
    print(id)
    parties = []

    author_party = create_author_party()
    parties.append(author_party)

    for i, signer in enumerate(signers, 2):
        email = signer.signer_email
        name = signer.signer_name
        delivery_method = signer.mode

        party = create_signer_party(email, name, sign_order=i, delivery_method=delivery_method)
        parties.append(party)

    tags = []
    for key, value in metadata.items():
        if key != 'title':  # Don't duplicate title in tags
            tags.append({
                "name": key,
                "value": str(value)
            })
    # Create document data without tags
    document_data = {
        "title": metadata.get('title', 'Document to Sign') if metadata else "Document to Sign",
        "parties": parties,
        "tags": tags
    }

    data = {
        "document_id": id,
        "document": json.dumps(document_data),
        #"tags": json.dumps(tags)
    }

    response = requests.post(
        BASE_URL + '/api/v2/documents/' + str(id) + '/update',
        data=data,
        headers=auth_headers
    ).json()

    if 'parties' not in response:
        raise Exception("No parties found in response")

    return response['parties']

def update_document_tags(document_id, metadata, auth_headers):
    """Update document tags using the dedicated tags endpoint"""
    if not metadata:
        return

    print("update_document_tags")

    # Convert metadata to Scrive tags format
    tags = []
    for key, value in metadata.items():
        if key != 'title':  # Don't duplicate title in tags
            tags.append({
                "name": key,
                "value": str(value)
            })

    if not tags:
        return

    url = f"{BASE_URL}/api/v2/documents/{document_id}/tags/update"
    data = {
        "document_id": document_id,
        "tags": json.dumps(tags)
    }

    response = requests.post(url, data=data, headers=auth_headers)

    print(response.content)
    if response.status_code != 200:
        print(f"Warning: Failed to update tags: {response.status_code} - {response.text}")
    else:
        print(f"Successfully updated tags for document {document_id}")



def start_process(id, auth_headers):
    print("start_process")
    url = BASE_URL + '/api/v2/documents/' + id + '/start'
    data = {"document_id": id}
    response = requests.post(url, data=data, headers=auth_headers).json()
    print("Getting start process")

    if 'parties' not in response:
        raise Exception(f"Failed to start document process. Status code: {response.status_code}")
    print("Returning json from start")
    return response['parties']

def get_sign_urls(parties):
    print("get_sign_urls")
    signing_urls = []
    for party in parties:
        email = party['fields'][0]['value']
        signing_url = party.get('api_delivery_url')
        delivery_method = party['delivery_method']
        signing_urls.append({
            "signer_email": email,
            "signing_url": signing_url,
            "mode": SigningMode.DIRECT_SIGNING if delivery_method == "api" else SigningMode.EMAIL_NOTIFICATION
        })
    return signing_urls

def initiate_signing_process(file, signers, metadata=None):
    auth_headers = login()
    id = new_request(file, auth_headers)
    update_with_signers(id, signers, auth_headers, metadata)

    # Start process FIRST (moves document to pending status)
    parties = start_process(id, auth_headers)

    # Update tags AFTER starting (when document is in pending status)
    #if metadata:
    #    update_document_tags(id, metadata, auth_headers)

    print(parties)
    urls = get_sign_urls(parties)
    return id, urls



def get_document_metadata(document_id):
    """
    Retrieve metadata from a Scrive document (document level only)
    """
    print(f"get_document_metadata for ID: {document_id}")

    try:
        auth_headers = login()
        url = f"{BASE_URL}/api/v2/documents/{document_id}/get"
        response = requests.get(url, headers=auth_headers)
        response.raise_for_status()

        document_data = response.json()
        metadata = {}

        # Extract from document-level tags (new format)
        if 'tags' in document_data:
            for tag in document_data['tags']:
                if isinstance(tag, dict) and 'name' in tag and 'value' in tag:
                    # New object format
                    metadata[tag['name']] = tag['value']
                elif isinstance(tag, str) and ':' in tag:
                    # Fallback for old string format
                    key, value = tag.split(':', 1)
                    metadata[key] = value

        # Add title if available
        if 'title' in document_data:
            metadata['title'] = document_data['title']

        return metadata

    except requests.exceptions.RequestException as e:
        print(f"Error getting document metadata: {e}")
        return {}


    except requests.exceptions.RequestException as e:
        print(f"Error getting document metadata: {e}")
        return {}

def get_document_status(document_id):
    print(f"get_document_status for ID: {document_id}")

    url = f"{BASE_URL}/api/v2/documents/{document_id}/get"

    try:
        auth_headers = login()
        response = requests.get(url, headers=auth_headers)
        response.raise_for_status()

        document_data = response.json()

        print(json.dumps(document_data, indent=4))

        # Extract relevant status information
        status_info = {
            'document_id': document_id,
            'status': document_data.get('status', 'unknown'),
            'signed': document_data.get('status') == 'closed',
            'parties': []
        }

        # Get signing status for each party/signer
        if 'parties' in document_data:
            for party in document_data['parties']:
                party_info = {
                    'email': party.get('fields', [{}])[0].get('value', 'unknown') if party.get('fields') else 'unknown',
                    'name': next((field.get('value') for field in party.get('fields', []) if field.get('type') == 'full_name'), 'unknown'),
                    'signed': party.get('sign_time') is not None,
                    'signed_at': party.get('sign_time'),
                    'delivery_method': party.get('delivery_method', 'unknown')
                }
                status_info['parties'].append(party_info)

        print(f"Document status: {status_info['status']}")
        print(f"Signed: {status_info['signed']}")
        print(f"Number of parties: {len(status_info['parties'])}")

        return status_info

    except requests.exceptions.RequestException as e:
        print(f"Error getting document status: {e}")
        raise Exception(f"Failed to get document status: {e}")

def get_document(document_id, signed=True):
    """
    Download a document from Scrive API

    Args:
        document_id (str): The ID of the document to download
        signed (bool): If True, download the signed version; if False, download original

    Returns:
        bytes: The document content as bytes
    """
    print(f"get_document for ID: {document_id}, signed: {signed}")
    auth_headers = login()

    if signed:
        url = f"{BASE_URL}/api/v2/documents/{document_id}/files/main"
    else:
        url = f"{BASE_URL}/api/v2/documents/{document_id}/files/main"

    try:
        response = requests.get(url, headers=auth_headers)
        response.raise_for_status()

        print(f"Downloaded document, size: {len(response.content)} bytes")
        return response.content

    except requests.exceptions.RequestException as e:
        print(f"Error downloading document: {e}")
        raise Exception(f"Failed to download document: {e}")

def save_document(document_id, output_path=None, signed=True):
    """
    Download and save a document from Scrive API to file
    """
    auth_headers = login()
    document_content = get_document(document_id, signed)

    if not output_path:
        suffix = "_signed" if signed else "_original"
        output_path = f"document_{document_id}{suffix}.pdf"

    with open(output_path, 'wb') as f:
        f.write(document_content)

    print(f"Document saved to: {output_path}")
    return output_path

async def search_documents(search_params, limit, offset):
    """Search Scrive documents using documentlist API"""
    try:
        auth_headers = login()

        # Scrive documentlist API endpoint
        url = f"{BASE_URL}/api/v2/documents/list"

        # Build query parameters for Scrive API
        params = {
            "max": limit,
            "offset": offset
        }

        # Add status filter if provided
        if search_params.get('status'):
            # Map common status values to Scrive status
            status_mapping = {
                'pending': 'preparation',
                'sent': 'pending',
                'completed': 'closed',
                'signed': 'closed'
            }
            scrive_status = status_mapping.get(search_params['status'].lower(), search_params['status'])
            params['filter'] = scrive_status

        response = requests.get(url, headers=auth_headers, params=params)
        response.raise_for_status()

        documents_data = response.json()
        results = []

        # Process each document and filter by metadata
        for doc in documents_data.get('documents', []):
            document_info = {
                'document_id': doc.get('id'),
                'title': doc.get('title', 'Untitled'),
                'status': doc.get('status'),
                'created_at': doc.get('created'),
                'modified_at': doc.get('modified'),
                'service': 'scrive',
                'metadata': {}
            }

            # Extract metadata from tags
            if 'tags' in doc:
                for tag in doc['tags']:
                    if isinstance(tag, dict) and 'name' in tag and 'value' in tag:
                        document_info['metadata'][tag['name']] = tag['value']
                    elif isinstance(tag, str) and ':' in tag:
                        key, value = tag.split(':', 1)
                        document_info['metadata'][key] = value

            # Add title to metadata if available
            if doc.get('title'):
                document_info['metadata']['title'] = doc['title']

            # Filter by metadata parameters (including handler and system)
            matches = True
            for param_key, param_value in search_params.items():
                if param_key == 'status':
                    continue  # Already handled above
                elif param_key == 'title':
                    if param_value.lower() not in document_info['title'].lower():
                        matches = False
                        break
                else:
                    # Check if metadata contains the search parameter
                    # This now includes 'handler' and 'system' automatically
                    doc_value = document_info['metadata'].get(param_key, '').lower()
                    if param_value.lower() not in doc_value:
                        matches = False
                        break

            if matches:
                results.append(document_info)

        logger.info(f"Found {len(results)} matching documents")
        return results

    except requests.exceptions.RequestException as e:
        logger.error(f"Scrive API error during search: {e}")
        raise Exception(f"Failed to search Scrive documents: {e}")
    except Exception as e:
        logger.error(f"Error searching Scrive documents: {e}")
        raise Exception(f"Failed to search documents: {e}")

if __name__ == "__main__":
    # Example with metadata at document level only
    metadata = {
        "project_id": "PROJ-1",
        "title": "Anställningskontrakt"
    }

    signers = [
        ("signer1@foo.bar", "signer1", "api"),
        ("signer2@foo.bar", "signer2", "api"),
    ]

    doc_id, urls = initiate_signing_process(FILE_PATH, signers, metadata)
