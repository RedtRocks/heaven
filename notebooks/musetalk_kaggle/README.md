# MuseTalk Kaggle kernel

Pushed by `backend/app/providers/face_musetalk_kaggle.py` (the `MuseTalkKaggleFaceRenderer`'s
`RealKaggleClient`), not run manually — but you can also push/run it by hand with the
`kaggle` CLI while setting things up:

```
kaggle kernels push -p notebooks/musetalk_kaggle
kaggle kernels status <your-username>/keepsake-musetalk
kaggle kernels output <your-username>/keepsake-musetalk -p /tmp/out
```

## Files

- `musetalk_kernel.py` — the script kernel. Clones MuseTalk, installs its deps, downloads
  weights (cached across runs in `/kaggle/working/MuseTalk` for as long as Kaggle keeps the
  session's working directory, which is not guaranteed between separate kernel runs — see
  the "unverified" note in `docs/notes/face-musetalk.md` about weight caching), renders one
  MP4 per WAV under `/kaggle/input/keepsake-face-jobs/jobs/*.wav` against the reference face
  in `/kaggle/input/keepsake-face-ref/`, and writes output to `/kaggle/working/out/`.
- `kernel-metadata.json` — kernel config (GPU on, internet on, the two dataset sources).
  **Replace `REPLACE_WITH_KAGGLE_USERNAME`** with the Owner's actual Kaggle username before
  the first push (matches `KAGGLE_KERNEL_ID` in `.env`).
- `dataset-metadata.json` — template for the `keepsake-face-jobs` dataset that
  `face_musetalk_kaggle.py` pushes new WAV versions to. Also needs the username filled in
  once, when the Owner creates the dataset the first time (see
  `docs/agents/reports/musetalk.md` for the exact one-time setup steps).

## One more dataset the code doesn't create for you

`keepsake-face-ref` (the Owner's reference face video/photo) isn't managed by the backend —
it's a one-time upload the Owner does by hand (record once, upload once). See
`docs/agents/reports/musetalk.md`.
