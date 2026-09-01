"""
Uploads new .run files from the local STS2 save history folder to the GCS
landing bucket. Intended to run unattended via Windows Task Scheduler.

Auth: run `gcloud auth application-default login` once on this machine
first (see docs/gcp_setup.md) — no service-account key file to manage.

Idempotency: a local manifest (uploaded_manifest.json, next to this script)
tracks which filenames have already been uploaded, so re-runs only upload
files that are new since the last run. This avoids re-listing/re-uploading
the whole bucket every run, which matters once the history folder has
thousands of files.

Configure via environment variables (or just edit the defaults below):
    STS2_SAVE_FOLDER   - local .run files folder
    STS2_GCS_BUCKET    - destination bucket name
    STS2_GCS_PREFIX    - destination path prefix inside the bucket
"""

import json
import os
from pathlib import Path

from google.cloud import storage

SAVE_FOLDER = Path(os.environ.get(
    "STS2_SAVE_FOLDER",
    r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292\profile1\saves\history",
))
BUCKET_NAME = os.environ.get("STS2_GCS_BUCKET", "REPLACE_WITH_YOUR_BUCKET_NAME")
GCS_PREFIX = os.environ.get("STS2_GCS_PREFIX", "raw")
MANIFEST_PATH = Path(__file__).parent / "uploaded_manifest.json"


def load_manifest() -> set[str]:
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text()))
    return set()


def save_manifest(uploaded: set[str]) -> None:
    MANIFEST_PATH.write_text(json.dumps(sorted(uploaded)))


def main():
    uploaded = load_manifest()

    local_files = {f.name for f in SAVE_FOLDER.glob("*.run")}
    new_files = sorted(local_files - uploaded)

    if not new_files:
        print("No new .run files to upload.")
        return

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    for filename in new_files:
        blob = bucket.blob(f"{GCS_PREFIX}/{filename}")
        blob.upload_from_filename(str(SAVE_FOLDER / filename))
        uploaded.add(filename)
        print(f"Uploaded {filename}")

    save_manifest(uploaded)
    print(f"Done. {len(new_files)} new file(s) uploaded to gs://{BUCKET_NAME}/{GCS_PREFIX}/")


if __name__ == "__main__":
    main()
