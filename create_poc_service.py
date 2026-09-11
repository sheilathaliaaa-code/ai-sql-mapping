import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("OM_HOST")
TOKEN = os.getenv("OM_TOKEN")

url = f"{BASE_URL}/v1/services/databaseServices"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

payload = {
    "name": "azuredevops_metadata_poc",
    "displayName": "Azure DevOps Metadata POC",
    "serviceType": "MySQL",
    "description": (
        "POC metadata container. "
        "Not connected to production database."
    )
}

response = requests.post(
    url,
    headers=headers,
    json=payload,
    timeout=30,
)

print("STATUS:", response.status_code)
print(response.text[:2000])