import os
import json
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Path to your service account key file
SERVICE_ACCOUNT_FILE = 'credentials.json'

# Authenticate with the service account
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/cloud-platform']
)

# Initialize Google API client
service = build('cloudcommerceprocurement', 'v1', credentials=credentials)

def fetch_entitlement_details(entitlement_id):
    """Fetch entitlement details from the Procurement API"""
    name = f'providers/DEMO-landgriffon/entitlements/4d37cff4-7830-49d2-a103-2f26313a10e4'
    request = service.providers().entitlements().get(name=name)
    response = request.execute()
    return response

# Test with the given entitlement ID
entitlement_id = '4d37cff4-7830-49d2-a103-2f26313a10e4'
details = fetch_entitlement_details(entitlement_id)
print(json.dumps(details, indent=2))
