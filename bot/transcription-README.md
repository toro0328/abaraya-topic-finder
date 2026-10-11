# Legacy transcription workflow

The old-show episodes are kept in `legacy-episodes.json` and addressed by IDs such as `legacy-135`. This workflow creates one Japanese, timestamped Whisper draft at a time and uploads it as an Actions artifact. It does not publish or commit generated transcripts.

## Run

1. Open **Actions → Transcribe a legacy episode → Run workflow**.
2. Enter its exact ID from `legacy-episodes.json` (for example `legacy-135` or `legacy-134-bonus`). This also handles the separately listed bonus episode 134. The script checks the legacy Seesaa RSS enclosure first.
3. If the feed no longer contains the episode, supply its direct HTTPS audio URL in `audio_url`.
4. Start with `tiny` for a quick connectivity check; choose `base` or `small` for a more accurate draft.
5. Download the artifact and review it before merging its episode entry into `legacy-transcripts.json`.

The source feed may only retain recent posts, and some Apple Podcasts episode pages do not expose a full-length audio URL. In those cases the run reports the missing source and exits without generating a transcript. The RSS parser and schema are tested offline.

## Data format

`legacy-transcripts.json` is keyed by the existing legacy episode ID. Each value records its source URL, model, generation time, review status, and timestamped segments. Generated text is explicitly marked `machine-generated-needs-review`; it should be checked before publication.
