# Component 4: Social Network Analysis for Hate-Speech Moderation

## 1. Purpose

Component 4 is the social-network-aware moderation layer of the hate-speech detection system. It combines:

1. An anonymised representation of a social-media discussion.
2. Hate-speech predictions from Components 1–3.
3. A directed interaction graph.
4. Network centrality measurements.
5. A persistent risk score for users.
6. Recommended escalation tiers.
7. Human moderator review.

The system does not automatically punish users. It generates an evidence-based recommendation, while the final decision remains with a human moderator.

The HTTP API is defined in [`backend/api/app.py`](./backend/api/app.py). The main processing logic is in [`backend/api/service.py`](./backend/api/service.py).

---

## 2. High-level workflow

```text
Social-media discussion
        |
        v
Browser extension captures comments and relationships
        |
        v
Users and relationships are anonymised
        |
        v
FastAPI backend stores the capture
        |
        +--> Classifier results arrive from Components 1–3
        |
        +--> Interaction graph is built
        |
        +--> Centrality is calculated
        |
        +--> Comment severity is calculated
        |
        +--> User risk is calculated
        |
        v
Recommended moderation tier
        |
        v
Human moderator review and decision
```

The core risk formula is:

```text
post contribution = total harmful severity × (1 + network influence)

user risk = sum of post contributions across captured posts
```

---

## 3. Input data

Component 4 receives two related inputs.

### 3.1 Anonymised social-network capture

The browser extension captures a post and its comments. A simplified capture looks like this:

```json
{
  "post_id": "post_123",
  "captured_at": "2026-10-14T00:19:55Z",
  "post_media": [],
  "comments": [
    {
      "comment_id": "comment_1",
      "post_id": "post_123",
      "type": "comment",
      "thread_root_id": null,
      "author_id": "u_abc123",
      "reply_to_id": null,
      "reply_to_ambiguous": false,
      "mentions": [],
      "text": "comment text",
      "media": []
    }
  ]
}
```

Important fields:

| Field | Meaning |
|---|---|
| `post_id` | Identifier for the captured post |
| `comment_id` | Identifier for an individual comment |
| `author_id` | Anonymised identifier of the author |
| `type` | `comment` for a top-level comment or `reply` for a reply |
| `thread_root_id` | Root comment of the reply chain |
| `reply_to_id` | Anonymised user targeted by the reply |
| `reply_to_ambiguous` | Whether the reply target could not be resolved confidently |
| `mentions` | Anonymised users mentioned in the comment |
| `text` | Text extracted from the comment |
| `media` | Images, GIFs, or other captured media |

The example files are [`sample_thread.json`](./backend/data/sample_thread.json) and [`synthetic_thread.json`](./backend/data/synthetic_thread.json).

### 3.2 Classifier results

Components 1–3 submit classification records using the comment ID:

```json
{
  "comment_id": "comment_1",
  "source_component": "sinhala-english",
  "predicted_category": "political",
  "confidence_score": 0.90
}
```

Supported categories include:

```text
racial_ethnic
religious
political
gender_based
sexual_orientation
hate_unspecified
not_hate
```

The classifier result is joined to the captured comment using:

```text
classifier.comment_id == capture_comment.comment_id
```

---

## 4. Browser extension workflow

The capture logic is implemented in [`extension/content/content.js`](../extension/content/content.js), and the service worker is in [`extension/background.js`](../extension/background.js).

### 4.1 Extracting comments

The extension reads the social-media page and extracts:

- Comment IDs.
- Author information.
- Whether an item is a comment or reply.
- Reply targets.
- Mentions.
- Text.
- Images and GIFs.
- The post ID.

The extension can try to expand hidden comments and replies using:

```text
Alt + Shift + E
```

This matters because the graph can only include comments that have been loaded and captured.

### 4.2 Anonymising users

Real user handles are converted into pseudonymous IDs using a locally stored random salt and SHA-256:

```text
real user handle -> u_<short hash>
```

For example:

```text
Alice -> u_71364afa66dc0a64
```

The backend therefore works with pseudonyms instead of real names.

### 4.3 Extension shortcuts

| Shortcut | Function |
|---|---|
| `Alt + Shift + E` | Expand more comments and replies |
| `Alt + Shift + C` | Inspect captured data in the browser console |
| `Alt + Shift + J` | Copy anonymised JSON to the clipboard |
| `Alt + Shift + U` | Send the anonymised capture to the local API |

When the capture is sent, the extension sends it to:

```text
POST http://127.0.0.1:8000/capture
```

---

## 5. Backend ingestion paths

### 5.1 Batch ingestion

The endpoint:

```text
POST /ingest
```

accepts the capture and classifier records together:

```json
{
  "capture": {
    "...": "anonymised capture"
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

This path is useful when the whole input is already available.

### 5.2 Live incremental processing

The live workflow uses:

```text
POST /capture
GET  /pending
POST /classifications
```

The capture can arrive before the classifier results.

1. `POST /capture` stores the post and scores currently available classifications.
2. `GET /pending` returns comments still waiting for classification.
3. `POST /classifications` stores new labels.
4. Affected posts are automatically rescored.

This logic is implemented in [`backend/api/live.py`](./backend/api/live.py).

The two sides can operate in either order. A post is rescored whenever new comments or new labels arrive.

---

## 6. Building the interaction graph

The graph logic is implemented in [`backend/graph/build_graph.py`](./backend/graph/build_graph.py).

The system creates a directed graph using NetworkX.

### 6.1 Graph nodes

The graph contains:

- One node for every anonymised user.
- One synthetic `POST` node representing the original post.

### 6.2 Graph edges

An edge means that one user directed an interaction toward another node.

#### Top-level comment

```text
Alice writes a top-level comment

Alice -> POST
```

#### Reply

```text
Bob replies to Alice

Bob -> Alice
```

#### Mention

```text
Charlie mentions Alice

Charlie -> Alice
```

If a comment contains both a reply and a mention to the same user, the target is only counted once for that comment.

If the reply target is ambiguous or missing, the implementation attempts to use the root comment author. If that cannot be found, it falls back to the `POST` node.

### 6.3 Edge weights

Repeated interactions increase the edge weight:

```text
Bob -> Alice, weight = 3
```

This means Bob interacted with Alice three times in the captured thread.

### 6.4 Example

Suppose the thread contains:

```text
Alice writes the original comment.
Bob replies to Alice.
Charlie replies to Alice.
Alice replies to Charlie.
David writes another top-level comment.
```

The graph contains edges similar to:

```text
Alice   -> POST
Bob     -> Alice
Charlie -> Alice
Alice   -> Charlie
David   -> POST
```

---

## 7. Centrality analysis

Centrality is implemented in [`backend/centrality/centrality.py`](./backend/centrality/centrality.py).

Centrality is applied only when the thread has:

```text
at least 15 comments
at least 6 unique users
```

Small threads still receive content-based severity scores, but their network influence is set to zero. This avoids making strong structural claims from very small samples.

### 7.1 In-degree

In-degree counts incoming relationships.

```text
Bob -> Alice
Charlie -> Alice
David -> Alice
```

Alice has an in-degree of 3.

It measures how many interactions are directed toward a user.

### 7.2 Out-degree

Out-degree counts outgoing relationships.

```text
Alice -> Bob
Alice -> Charlie
Alice -> David
```

Alice has an out-degree of 3.

It measures how many distinct interaction targets a user creates.

The system reports out-degree, but the final influence formula currently uses in-degree and betweenness.

### 7.3 Betweenness centrality

Betweenness centrality measures how often a user lies on shortest paths between other nodes.

A user with high betweenness may connect otherwise separate groups:

```text
Group A <-> central user <-> Group B
```

This can indicate a bridging position in the conversation.

---

## 8. Calculating network influence

The system normalises each user's centrality relative to the maximum value in the same thread:

```text
normalised in-degree =
    user's in-degree centrality / maximum in-degree centrality

normalised betweenness =
    user's betweenness / maximum betweenness
```

The influence score is:

```text
influence =
    (normalised in-degree + normalised betweenness) / 2
```

The result is between `0` and `1`.

| Influence | Interpretation |
|---:|---|
| `0` | No measurable influence, or centrality was not applied |
| `0.25` | Low influence |
| `0.50` | Moderate influence |
| `1.00` | Highest combined influence in that thread |

The score is thread-relative. An influence of `1.0` means the user is the strongest user in that captured thread, not that the user is globally influential on the platform.

Centrality alone never creates a flagged user. A user must first have at least one comment with positive severity.

---

## 9. Calculating comment severity

The classification and severity logic is in [`backend/risk_scoring/severity.py`](./backend/risk_scoring/severity.py). Configuration is in [`backend/risk_scoring/config.py`](./backend/risk_scoring/config.py).

The current formula is:

```text
severity = confidence × category_weight
```

All current category weights are `1.0`, so severity currently equals confidence for valid harmful predictions.

Example:

```text
category weight = 1.0
confidence = 0.80

severity = 0.80 × 1.0 = 0.80
```

The confidence floor is `0.5`.

```text
confidence < 0.5 -> severity = 0
```

The `not_hate` category always receives zero severity.

The system distinguishes:

```text
severity = 0     classified as not harmful or below the confidence floor
severity = null  no classifier result is available yet
```

An unclassified comment is not treated as safe.

### Multiple classifier sources

A comment may have multiple records, for example one from a text model and one from the meme model:

```json
[
  {
    "comment_id": "comment_10",
    "source_component": "sinhala-english",
    "predicted_category": "gender_based",
    "confidence_score": 0.55
  },
  {
    "comment_id": "comment_10",
    "source_component": "meme",
    "predicted_category": "hate_unspecified",
    "confidence_score": 0.70
  }
]
```

The highest calculated severity is selected:

```text
max(0.55, 0.70) = 0.70
```

This is currently a maximum-severity fusion strategy.

---

## 10. Per-user aggregation

After comments are scored, the system groups them by author and calculates:

- Total number of comments.
- Number of unclassified comments.
- Number of flagged comments.
- Total severity.
- Maximum severity.

Example:

```text
User: u_alice

Comment 1 severity: 0.80
Comment 2 severity: 0.60
Comment 3 severity: 0.00

Flagged comments: 2
Total severity: 1.40
```

Only users with at least one flagged comment are stored in the risk store.

---

## 11. Combining harmful content and network influence

For each flagged user in a post:

```text
post contribution =
    total severity × (1 + influence)
```

Example:

```text
total severity = 2.0
influence = 0.5

contribution = 2.0 × (1 + 0.5)
             = 3.0
```

If the thread is too small for centrality:

```text
influence = 0
contribution = total severity
```

This means a user cannot receive additional risk merely because they are central. Positive harmful severity is required first.

The implementation is in [`backend/risk_scoring/risk.py`](./backend/risk_scoring/risk.py).

---

## 12. Persistent risk across posts

The user risk score is the sum of contributions across all captured posts:

```text
user risk =
    contribution from Post A
  + contribution from Post B
  + contribution from Post C
```

Example:

```text
Post A: 1.20
Post B: 2.10
Post C: 0.80

Total risk: 4.10
```

The current score does not decay over time.

### Duplicate capture protection

If the same post is captured again, its previous contribution is removed before the new contribution is stored. Therefore, recapturing a post replaces its old entry rather than double-counting it.

This is useful when:

- More replies become visible.
- A classifier produces an updated result.
- The original capture was incomplete.

---

## 13. Recommended escalation tiers

Risk thresholds are defined in [`backend/escalation/tiers.py`](./backend/escalation/tiers.py).

Current thresholds:

| Risk score | Recommendation |
|---:|---|
| Below `1.0` | `none` |
| `1.0` or above | `warning` |
| `3.0` or above | `flag` |
| `6.0` or above | `high_severity_report` |

Example:

```text
Risk 0.80 -> none
Risk 1.40 -> warning
Risk 3.50 -> flag
Risk 7.20 -> high_severity_report
```

These are recommendations and currently documented as placeholder thresholds to be tuned using real evaluation data.

---

## 14. Justification and moderator review

The dashboard obtains users through:

```text
GET /users
```

It can then request a user explanation through:

```text
GET /users/{user_id}/justification
```

The response includes:

- Persistent risk.
- Recommended tier.
- Contributing posts.
- Number of flagged comments.
- Categories.
- Confidence values.
- Severity values.
- In-degree and betweenness components.
- Influence.
- Contribution arithmetic.
- Review status.

The explanation logic is in [`backend/justification/justify.py`](./backend/justification/justify.py).

The system verifies that the explanation agrees with the stored calculations before returning it.

### Human decision

The moderator can accept the recommendation:

```json
{
  "decision": "accept",
  "reviewer": "moderator_01",
  "note": ""
}
```

Or override it:

```json
{
  "decision": "override",
  "reviewer": "moderator_01",
  "note": "The classifier misunderstood the context.",
  "final_tier": "none"
}
```

An override requires a written reason and a final tier different from the recommendation.

Review decisions are stored in an append-only JSON Lines log by [`backend/escalation/review.py`](./backend/escalation/review.py).

The system does not automatically ban, block, delete, or report a user.

---

## 15. Storage

The prototype uses JSON files under:

```text
component-4-social-network/backend/data/captures/
```

| File | Purpose |
|---|---|
| `capture_store.json` | Captured anonymised posts and comments |
| `classifier_store.json` | Classifier records indexed by comment ID |
| `risk_store.json` | Persistent per-user risk contributions |
| `review_log.jsonl` | Human moderator decisions |

The live store operations are implemented in [`backend/api/live.py`](./backend/api/live.py), while batch risk-store operations are implemented in [`backend/api/service.py`](./backend/api/service.py) and [`backend/risk_scoring/risk.py`](./backend/risk_scoring/risk.py).

---

## 16. Complete numerical example

Assume a thread contains:

```text
15 comments
6 unique users
```

User `u_a` has two harmful comments:

```text
Comment 1: political, confidence 0.90
Comment 2: religious, confidence 0.80
```

Because the current weights are `1.0`:

```text
total severity = 0.90 + 0.80 = 1.70
```

Suppose network analysis produces:

```text
normalised in-degree = 0.80
normalised betweenness = 0.40
```

Then:

```text
influence = (0.80 + 0.40) / 2
          = 0.60
```

The post contribution is:

```text
contribution = 1.70 × (1 + 0.60)
             = 2.72
```

If the user already had `0.80` risk:

```text
previous risk = 0.80
new contribution = 2.72
total risk = 3.52
```

Since `3.52` is above the `3.0` threshold:

```text
recommended tier = flag
```

A moderator then reviews the evidence and accepts or overrides the recommendation.

---

## 17. Limitations and interpretation

### Incomplete captures

The graph only contains comments and replies successfully loaded by the extension. Hidden, collapsed, deleted, or unavailable comments are not represented.

### Thread-relative influence

Centrality is calculated within one captured thread. It is not a measure of global platform influence.

### Equal category weights

All categories currently have weight `1.0`. No category is intentionally ranked above another yet.

### No time decay

Old contributions remain in the persistent risk score. A production version may need time decay, review expiry, or separate recent and historical scores.

### Centrality does not prove intent

A highly central user may be defending others, moderating a conversation, or receiving attacks. Network position is not proof of harmful intent.

### Ambiguous replies

The social-media page may not expose a reliable reply target. The extension records this uncertainty using `reply_to_ambiguous`, and the graph builder uses a fallback target when necessary.

---

## 18. Summary

Component 4 works as a six-stage pipeline:

```text
1. Capture
   Collect anonymised users, comments, replies, mentions, and media.

2. Classify
   Receive hate-speech predictions from Components 1–3.

3. Build graph
   Convert replies and mentions into directed graph edges.

4. Measure influence
   Calculate in-degree and betweenness centrality.

5. Score risk
   Combine harmful severity and network influence.

6. Review
   Accumulate risk, recommend a tier, and let a moderator decide.
```

The central principle is:

```text
harmful content severity
    adjusted by network influence
    accumulated across posts
    presented for human review
```

The system recommends an action; a human moderator makes the final decision.
