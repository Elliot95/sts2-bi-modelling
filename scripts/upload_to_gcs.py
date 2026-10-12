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

Save folders: the game keeps one history folder per profile, and a separate
tree for modded play (steam/<id>/modded/profileN/...). profile1 is uploaded
from both trees (HISTORY_GLOBS). profile1 files go to raw/<file> (as they always have); others go to
raw/<relative folder>/<file>, e.g. raw/modded/profile1/<file>, which the
loader turns into fact_run.save_source (Vanilla / Modded / Profile N).

Configure via environment variables (or just edit the defaults below):
    STS2_SAVE_ROOT     - the game's steam/<steam id> folder
    STS2_GCS_BUCKET    - destination bucket name
    STS2_GCS_PREFIX    - destination path prefix inside the bucket
"""

import json
import os
from pathlib import Path

from google.cloud import storage

SAVE_ROOT = Path(os.environ.get(
    "STS2_SAVE_ROOT",
    r"C:\Users\1995e\AppData\Roaming\SlayTheSpire2\steam\76561199024701292",
))
# Folders under SAVE_ROOT that hold run history: the main profile, vanilla and
# modded. Other profiles (e.g. profile2, a few old test runs) are deliberately left out.
HISTORY_GLOBS = ("profile1/saves/history", "modded/profile1/saves/history")
BUCKET_NAME = os.environ.get("STS2_GCS_BUCKET", "")
GCS_PREFIX = os.environ.get("STS2_GCS_PREFIX", "raw")
MANIFEST_PATH = Path(__file__).parent / "uploaded_manifest.json"


def load_manifest() -> set[str]:
    if MANIFEST_PATH.exists():
        return set(json.loads(MANIFEST_PATH.read_text()))
    return set()


def save_manifest(uploaded: set[str]) -> None:
    MANIFEST_PATH.write_text(json.dumps(sorted(uploaded)))


def main():
    # Fail fast on misconfiguration. A missing bucket used to fall back to a
    # placeholder name, which only surfaced as an error once there were new
    # runs to upload (see docs/audit.md, F1).
    if not BUCKET_NAME:
        raise SystemExit("STS2_GCS_BUCKET is not set. Run: setx STS2_GCS_BUCKET <bucket-name>")
    folders = [f for g in HISTORY_GLOBS for f in sorted(SAVE_ROOT.glob(g)) if f.is_dir()]
    if not folders:
        raise SystemExit(f"No save history folders found under {SAVE_ROOT}")

    uploaded = load_manifest()

    # filename -> local path. Run files are named by start time, so names are
    # unique across folders and the manifest can stay keyed by filename.
    local_files = {f.name: f for folder in folders for f in folder.glob("*.run")}
    new_files = sorted(set(local_files) - uploaded)

    if not new_files:
        print("No new .run files to upload.")
        return

    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    for filename in new_files:
        path = local_files[filename]
        rel = path.parent.parent.parent.relative_to(SAVE_ROOT).as_posix()   # e.g. modded/profile1
        prefix = GCS_PREFIX if rel == "profile1" else f"{GCS_PREFIX}/{rel}"
        blob = bucket.blob(f"{prefix}/{filename}")
        blob.upload_from_filename(str(path))
        uploaded.add(filename)
        # Save after every file so a mid-batch failure doesn't lose track of
        # what already uploaded (audit F9).
        save_manifest(uploaded)
        print(f"Uploaded {filename}")

    print(f"Done. {len(new_files)} new file(s) uploaded to gs://{BUCKET_NAME}/{GCS_PREFIX}/")


if __name__ == "__main__":
    main()
