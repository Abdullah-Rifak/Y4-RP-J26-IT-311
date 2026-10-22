# Component 4: Social Network Analysis

Component 4 is the social-network-aware moderation component of the hate-speech detection system. It combines anonymised discussion data with predictions from Components 1–3 to identify users whose harmful comments may have a significant position in the discussion network.

This component is a **moderation recommendation system**. It does not automatically ban users, delete comments, or apply account sanctions. A human moderator reviews the evidence and records the final decision.

For the detailed system explanation, see [`SOCIAL_NETWORK_ANALYSIS.md`](./SOCIAL_NETWORK_ANALYSIS.md).

---

## Features

- Captures public Facebook comment threads through a browser extension.
- Removes direct user identity by generating pseudonymous user IDs.
- Represents replies and mentions as a directed interaction graph.
- Calculates in-degree, out-degree, and betweenness centrality.
- Joins hate-speech predictions from Components 1–3 to captured comments.
- Calculates comment severity using confidence and category weights.
- Adjusts harmful-content risk using relative network influence.
- Maintains persistent per-user risk across captured posts.
- Replaces previous results when the same post is captured again.
- Provides recommended moderation tiers.
- Generates verifiable, plain-language justifications.
- Records human accept or override decisions.
- Provides a React dashboard for moderator review.

---

## Architecture

```text
Facebook discussion
        |
        v
Browser extension
        |
        | anonymised capture
        v
FastAPI backend
        |
        +--> Capture storage
        +--> Classifier-result storage
        +--> Interaction graph
        +--> Centrality analysis
        +--> Severity and risk scoring
        +--> Escalation recommendation
        |
        v
React moderation dashboard
        |
        v
Human moderator decision
```

Main directories:

```text
backend/
  api/             FastAPI routes and ingestion services
  centrality/      Network centrality calculations
  data/            Sample inputs and local capture storage
  escalation/      Tier recommendations and review decisions
  evaluation/      Evaluation and benchmarking utilities
  graph/           Interaction-graph construction
  justification/   Human-readable evidence generation
  risk_scoring/    Severity and persistent risk calculations
  tools/           Demonstration classifier utilities

dashboard/         React/Vite moderation dashboard
extension/         Browser extension for Facebook capture
tests/             Backend tests
```

---

## Processing workflow

### 1. Capture

The browser extension extracts:

- Post ID.
- Comment IDs.
- Anonymised authors.
- Top-level comments and replies.
- Reply targets.
- Mentions.
- Text.
- Images and GIFs.

The extension uses these shortcuts:

| Shortcut | Purpose |
|---|---|
| `Alt + Shift + E` | Expand more comments and replies |
| `Alt + Shift + C` | Inspect captured data in the browser console |
| `Alt + Shift + J` | Copy anonymised JSON to the clipboard |
| `Alt + Shift + U` | Send the capture to the local API |

The extension sends captures to:

```text
POST http://127.0.0.1:8000/capture
```

### 2. Classification

Components 1–3 submit predictions using the captured `comment_id`:

```json
{
  "comment_id": "9000001",
  "source_component": "sinhala-english",
  "predicted_category": "political",
  "confidence_score": 0.90
}
```

Supported categories currently include:

```text
racial_ethnic
religious
political
gender_based
sexual_orientation
hate_unspecified
not_hate
```

### 3. Graph construction

The graph is directed:

```text
top-level comment: User -> POST
reply:             User -> replied-to-user
mention:           User -> mentioned-user
```

Repeated interactions increase the edge weight.

Graph construction is implemented in [`backend/graph/build_graph.py`](./backend/graph/build_graph.py).

### 4. Centrality

Centrality is applied only when a thread contains:

```text
at least 15 comments
at least 6 unique users
```

The system calculates:

- In-degree centrality.
- Out-degree centrality.
- Betweenness centrality.

The influence score is:

```text
influence =
    (normalised in-degree + normalised betweenness) / 2
```

If a thread is too small, influence is set to zero.

### 5. Severity

For a harmful classifier prediction:

```text
severity = confidence × category_weight
```

All category weights are currently `1.0`. Predictions below the confidence floor of `0.5` contribute zero severity. `not_hate` also contributes zero severity.

If several components classify the same comment, the highest calculated severity is currently selected.

### 6. Risk

For each flagged user in a post:

```text
post contribution =
    total severity × (1 + influence)
```

Across multiple posts:

```text
user risk = sum of all post contributions
```

Only users with at least one positive-severity comment are stored.

### 7. Moderation recommendation

The current thresholds are:

| Risk | Recommendation |
|---:|---|
| Below `1.0` | `none` |
| `1.0` or above | `warning` |
| `3.0` or above | `flag` |
| `6.0` or above | `high_severity_report` |

These are recommendations only and are intended to be tuned using evaluation data.

---

## Backend setup

Open a terminal in the backend directory:

```powershell
cd component-4-social-network\backend
```

Install the Python dependencies used by the backend:

```powershell
python -m pip install fastapi uvicorn pydantic networkx pytest
```

Start the API:

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

The interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

Check that the API is running:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The health response includes the available escalation tiers.

---

## Dashboard setup

Open a second terminal in the dashboard directory:

```powershell
cd component-4-social-network\dashboard
npm install
npm run dev
```

Open the Vite URL displayed in the terminal, normally:

```text
http://localhost:5173
```

The dashboard connects to:

```text
http://127.0.0.1:8000
```

To use another backend URL, create a `.env` file in `dashboard/`:

```text
VITE_API_URL=http://127.0.0.1:8000
```

---

## Browser extension setup

1. Start the backend API.
2. Open Chrome or a Chromium-based browser.
3. Open the extensions page:

   ```text
   chrome://extensions
   ```

4. Enable **Developer mode**.
5. Select **Load unpacked**.
6. Choose the [`extension`](./extension/) directory.
7. Open a public Facebook post.
8. Use `Alt + Shift + E` to expand comments if necessary.
9. Use `Alt + Shift + U` to send the anonymised capture.

The extension manifest is in [`extension/manifest.json`](./extension/manifest.json).

---

## API routes

### Health

```text
GET /health
```

### Batch ingestion

```text
POST /ingest
```

Request body:

```json
{
  "capture": {
    "post_id": "post_123",
    "comments": []
  },
  "classifier": [
    {
      "comment_id": "comment_1",
      "source_component": "tamil-english",
      "predicted_category": "racial_ethnic",
      "confidence_score": 0.86
    }
  ]
}
```

### Live capture

```text
POST /capture
```

Stores a capture and scores it using currently available classifier results.

### Pending classification work

```text
GET /pending
GET /pending?kind=text
GET /pending?kind=media&source=meme
```

Returns comments that still need a classifier result.

### Add classifier results

```text
POST /classifications
```

Request body:

```json
[
  {
    "comment_id": "comment_1",
    "source_component": "sinhala-english",
    "predicted_category": "political",
    "confidence_score": 0.90
  }
]
```

Affected posts are automatically rescored.

### List users

```text
GET /users
GET /users?min_tier=flag
```

### Get a user justification

```text
GET /users/{user_id}/justification
```

### Get previous moderator decisions

```text
GET /users/{user_id}/decisions
```

### Record a moderator decision

```text
POST /users/{user_id}/decisions
```

Accept a recommendation:

```json
{
  "decision": "accept",
  "reviewer": "moderator_01",
  "note": ""
}
```

Override a recommendation:

```json
{
  "decision": "override",
  "reviewer": "moderator_01",
  "note": "The classifier misunderstood the context.",
  "final_tier": "none"
}
```

An override requires a written reason and a final tier different from the recommendation.

---

## Command-line examples

Run graph construction:

```powershell
cd component-4-social-network\backend
python -m graph.build_graph data\synthetic_thread.json
```

Run centrality analysis:

```powershell
python -m centrality.centrality data\synthetic_thread.json
```

Run severity attachment:

```powershell
python -m risk_scoring.severity data\synthetic_thread.json data\synthetic_classifier.json
```

Run persistent risk scoring:

```powershell
python -m risk_scoring.risk data\synthetic_thread.json data\synthetic_classifier.json
```

Generate stored-user justifications:

```powershell
python -m justification.justify --all
```

Generate one user's justification:

```powershell
python -m justification.justify --user u_syn_a
```

The sample and synthetic inputs are in [`backend/data`](./backend/data/).

---

## Running tests

From the Component 4 directory:

```powershell
cd component-4-social-network
pytest tests
```

Run dashboard tests:

```powershell
cd component-4-social-network\dashboard
npm test
```

Build the dashboard:

```powershell
npm run build
```

---

## Storage

The prototype stores local JSON data under:

```text
backend\data\captures\
```

Important files:

| File | Purpose |
|---|---|
| `capture_store.json` | Captured anonymised posts and comments |
| `classifier_store.json` | Classifier records indexed by comment ID |
| `risk_store.json` | Persistent per-user risk contributions |
| `review_log.jsonl` | Append-only moderator decisions |

The same post is not double-counted. Recapturing a post replaces its previous contribution.

---

## Privacy and interpretation

- User identifiers sent to the backend are pseudonymous.
- The graph only represents captured comments and replies.
- A missing or unclassified comment is not proof that the comment is safe.
- Centrality is relative to one captured thread, not the entire social platform.
- High centrality does not prove harmful intent.
- The current risk score does not decay over time.
- The current category weights and escalation thresholds are research-prototype values.
- The system provides recommendations; moderators make final decisions.

---

## Detailed documentation

For the complete explanation of inputs, processing stages, formulas, examples, limitations, and data workflow, read [`SOCIAL_NETWORK_ANALYSIS.md`](./SOCIAL_NETWORK_ANALYSIS.md).
