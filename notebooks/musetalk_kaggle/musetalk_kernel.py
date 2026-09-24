"""Kaggle script kernel: renders MuseTalk videos for a batch of WAV files.

Pushed by `backend/app/providers/face_musetalk_kaggle.py` via the Kaggle API. Not imported
by the backend at runtime — the backend only pushes this file's *text* as the kernel's code.

Inputs (attached as Kaggle dataset_sources, see kernel-metadata.json):
  - /kaggle/input/keepsake-face-ref/face.mp4 (or .jpg/.png)
      The Owner's reference face video/photo. Recorded once by the Owner (see
      docs/notes/face-musetalk.md and docs/agents/reports/musetalk.md for how).
  - /kaggle/input/keepsake-face-jobs/jobs/*.wav
      One or more WAVs to render. The provider pushes a new *version* of this dataset per
      job (or batches several WAVs into one version) rather than creating a new dataset
      each time, since free Kaggle accounts have a dataset-count quota.

Output:
  - /kaggle/working/out/<job_id>.mp4 for each /kaggle/input/keepsake-face-jobs/jobs/<job_id>.wav

This script is deliberately defensive about MuseTalk's exact CLI/output layout (see the
"unverified" notes in docs/notes/face-musetalk.md) — it globs for outputs rather than
assuming an exact filename, and fails loudly (non-zero exit) if nothing was produced, so a
failed run shows up as an "error"-ish Kaggle kernel status rather than silently succeeding.
"""

import glob
import json
import os
import shutil
import subprocess
import sys

MUSETALK_DIR = "/kaggle/working/MuseTalk"
REF_DIR = "/kaggle/input/keepsake-face-ref"
JOBS_DIR = "/kaggle/input/keepsake-face-jobs/jobs"
OUT_DIR = "/kaggle/working/out"
RESULT_DIR = "/kaggle/working/MuseTalk/results/keepsake"


def sh(cmd: list[str], **kw) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def find_reference() -> str:
    for ext in ("mp4", "mov", "jpg", "jpeg", "png"):
        matches = glob.glob(f"{REF_DIR}/*.{ext}")
        if matches:
            return matches[0]
    raise FileNotFoundError(
        f"No reference face video/image found under {REF_DIR}. "
        "Expected the keepsake-face-ref dataset to contain face.mp4 (or .jpg/.png)."
    )


def setup_musetalk() -> None:
    if not os.path.isdir(MUSETALK_DIR):
        sh(["git", "clone", "--depth", "1", "https://github.com/TMElyralab/MuseTalk.git", MUSETALK_DIR])
    sh([sys.executable, "-m", "pip", "install", "-q", "-r", f"{MUSETALK_DIR}/requirements.txt"])
    sh([sys.executable, "-m", "pip", "install", "-q", "openmim"])
    sh([sys.executable, "-m", "mim", "install", "-q", "mmengine"])
    sh([sys.executable, "-m", "mim", "install", "-q", "mmcv==2.0.1"])
    sh([sys.executable, "-m", "pip", "install", "-q", "mmdet==3.1.0", "mmpose==1.1.0"])
    weights_marker = f"{MUSETALK_DIR}/models/musetalkV15/unet.pth"
    if not os.path.exists(weights_marker):
        download_script = f"{MUSETALK_DIR}/download_weights.sh"
        if os.path.exists(download_script):
            sh(["bash", download_script], cwd=MUSETALK_DIR)
        else:
            raise FileNotFoundError(
                "MuseTalk's download_weights.sh is missing; see "
                "https://github.com/TMElyralab/MuseTalk for manual weight download steps."
            )


def build_inference_config(reference: str, wav_paths: list[str], config_path: str) -> dict[str, str]:
    """Writes MuseTalk's YAML config mapping each job's audio to the same reference face.

    Returns a dict of {job_id: expected_output_stem} for later matching against whatever
    MuseTalk actually names its output files.
    """
    import yaml  # PyYAML ships with MuseTalk's requirements.txt

    entries = {}
    job_ids = {}
    for wav_path in wav_paths:
        job_id = os.path.splitext(os.path.basename(wav_path))[0]
        entries[job_id] = {"video_path": reference, "audio_path": wav_path}
        job_ids[job_id] = job_id
    with open(config_path, "w") as f:
        yaml.safe_dump(entries, f)
    return job_ids


def run_inference(config_path: str) -> None:
    sh(
        [
            sys.executable,
            "-m",
            "scripts.inference",
            "--inference_config",
            config_path,
            "--result_dir",
            RESULT_DIR,
            "--unet_model_path",
            f"{MUSETALK_DIR}/models/musetalkV15/unet.pth",
            "--unet_config",
            f"{MUSETALK_DIR}/models/musetalkV15/musetalk.json",
            "--version",
            "v15",
        ],
        cwd=MUSETALK_DIR,
    )


def collect_outputs(job_ids: dict[str, str]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    produced = sorted(glob.glob(f"{RESULT_DIR}/**/*.mp4", recursive=True))
    if not produced:
        raise RuntimeError(f"MuseTalk produced no .mp4 files under {RESULT_DIR}")

    remaining = list(produced)
    for job_id in job_ids:
        # Prefer an output whose filename contains the job_id (MuseTalk usually names
        # outputs after the audio/video stem); fall back to consuming files in order if
        # the naming convention doesn't match (see docs/notes/face-musetalk.md).
        match = next((p for p in remaining if job_id in os.path.basename(p)), None)
        if match is None and remaining:
            match = remaining[0]
        if match is None:
            print(f"WARNING: no output found for job {job_id}", flush=True)
            continue
        remaining.remove(match)
        shutil.copyfile(match, f"{OUT_DIR}/{job_id}.mp4")

    manifest = {"jobs": sorted(os.listdir(OUT_DIR))}
    with open(f"{OUT_DIR}/manifest.json", "w") as f:
        json.dump(manifest, f)
    print(f"Wrote {len(manifest['jobs'])} video(s) to {OUT_DIR}", flush=True)


def main() -> None:
    wav_paths = sorted(glob.glob(f"{JOBS_DIR}/*.wav"))
    if not wav_paths:
        raise FileNotFoundError(f"No WAV files found under {JOBS_DIR}")

    setup_musetalk()
    reference = find_reference()
    config_path = "/kaggle/working/keepsake_inference.yaml"
    job_ids = build_inference_config(reference, wav_paths, config_path)
    run_inference(config_path)
    collect_outputs(job_ids)


if __name__ == "__main__":
    main()
