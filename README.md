# BrainImagingRepositoryFeedbacks

Minimal end-to-end scaffold for collecting user feedback from brain-imaging
data repositories, converting each submission into a GitHub-issue-shaped JSON
payload, and summarizing the collected feedback by topic.

## What is included

- **Front-end widget** in `/home/runner/work/BrainImagingRepositoryFeedbacks/BrainImagingRepositoryFeedbacks/frontend/widget.js`
  that can be embedded on a repository web page.
- **Example page** in `/home/runner/work/BrainImagingRepositoryFeedbacks/BrainImagingRepositoryFeedbacks/frontend/index.html`
  for local testing.
- **Python back-end** in `/home/runner/work/BrainImagingRepositoryFeedbacks/BrainImagingRepositoryFeedbacks/backend/app.py`
  that:
  - accepts feedback over HTTP,
  - stores every submission as JSON,
  - writes a companion GitHub issue payload JSON file,
  - refreshes topic summaries after each submission.

The implementation is dependency-free so it can run immediately. It is designed
so the generated issue JSON can later be handed to automation such as
[`github/issue-parser`](https://github.com/github/issue-parser), while topic
summaries can later be upgraded to an external Python LLM package if desired.

## Run locally

From `/home/runner/work/BrainImagingRepositoryFeedbacks/BrainImagingRepositoryFeedbacks`:

```bash
python -m backend.app --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.

Opening `frontend/index.html` directly lets you view and type into the form,
but sending feedback requires the server and the URL above.

## API

### `POST /api/feedback`

Accepts JSON like:

```json
{
  "name": "Researcher",
  "email": "researcher@example.org",
  "source_url": "https://example.org/datasets/study-1",
  "category": "bug",
  "message": "The download button fails for the BIDS archive."
}
```

Each request creates:

- `data/feedback/<uuid>.json` for the raw feedback record
- `data/issues/<uuid>.json` for the GitHub issue payload
- `data/summaries/topics.json` for the refreshed topic summary

### `GET /api/summary`

Returns the latest topic aggregation.

## Tests

Run the focused unit tests with:

```bash
python -m unittest discover -s tests
```
