import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ORG = os.getenv("AZDO_ORG")
PROJECT = os.getenv("AZDO_PROJECT")
REPO = os.getenv("AZDO_REPO")
PAT = os.getenv("AZDO_PAT")

FILE_PATH = (
    "/sql/report/report_powerbi/views/"
    "r00200_fut_view_SalesUtilization_PKTMonitoring.sql"
)

if not all([ORG, PROJECT, REPO, PAT]):
    raise RuntimeError("Konfigurasi .env belum lengkap.")

url = (
    f"https://dev.azure.com/{ORG}/{PROJECT}"
    f"/_apis/git/repositories/{REPO}/items"
)

params = {
    "path": FILE_PATH,
    "includeContent": "true",
    "api-version": "7.1",
}

response = requests.get(
    url,
    params=params,
    auth=("", PAT),
    timeout=30,
)

print("HTTP Status:", response.status_code)

if response.status_code != 200:
    print(response.text)
    raise SystemExit(1)

content = response.text

output_dir = Path("output")
output_dir.mkdir(exist_ok=True)

output_file = output_dir / "sample_view.sql"
output_file.write_text(content, encoding="utf-8")

print("\n✅ SQL berhasil diambil dari Azure DevOps")
print("File:", FILE_PATH)
print("Disimpan ke:", output_file)
print("Jumlah karakter:", len(content))