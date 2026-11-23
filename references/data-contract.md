# Data Contract

The engine stores operational data in local SQLite. Never commit the data
directory, exported lead files, credentials, or production logs to a public
repository.

## Campaign Configuration

`assets/campaign.example.json` is the canonical example.

Required sections:

- `campaign`: stable ID, display name, public base URL, timezone.
- `offer`: title, concrete promise, delivery URL and instruction.
- `capture`: consent text/version, privacy URL, response wording.
- `scoring`: thresholds, intent keywords, goal bonuses, exclusions.
- `automation`: enable switch, acknowledgement, alert, nurture schedule.
- `email`: sender settings using environment-variable names only.
- `webhook`: CRM/alert URL held in an environment variable.
- `retention_days`: maximum person-level retention.
- `messages`: pre-approved transactional and nurture templates.

Secret environment variables are read only at send time. The configuration may
contain the variable name, never its value.

## Lead Record

| Field | Meaning |
| --- | --- |
| `id` | Stable internal UUID |
| `campaign_id` | Campaign namespace for deduplication |
| `created_at`, `updated_at` | UTC timestamps |
| `source_channel` | `douyin`, `x`, `wechat-mp`, `owned-site`, or manual import |
| `source_type` | `landing_form`, `comment`, `dm`, `keyword_reply`, `manual` |
| `source_code` | Content/asset attribution code |
| `display_name` | Optional name supplied by the lead |
| `contact_type` | `email` or `wechat` |
| `contact_value` | Minimal contact needed for follow-up; local data only |
| `intent_text` | The person's own words |
| `pain_point`, `primary_goal` | Optional first-party answers |
| `consent_version`, `consent_at` | Affirmative opt-in evidence |
| `score`, `priority`, `score_reasons` | Observable, deterministic qualification |
| `status` | Pipeline state |
| `owner` | Human responsible for the next step |
| `next_action_at` | Queue deadline |
| `retention_until` | Person-level deletion deadline |
| `dedupe_key` | Hash-based duplicate key; no raw contact |

Allowed statuses:

```text
new
needs_human_reply
nurturing
qualified
contact_attempted
meeting_booked
won
lost
unsubscribed
```

Every change creates an immutable `events` row. Do not overwrite funnel
history.

## Outbox

The outbox has one message per lead, sequence, and campaign. It records:

- approved template name;
- channel and destination;
- scheduled time;
- status (`pending`, `sending`, `sent`, `failed`, `cancelled`);
- attempt count and last error;
- rendered subject/body.

Only `messages` templates may be rendered. Do not let an LLM invent and send a
new message directly to a customer without an approval gate.

## Import Format for User-Provided Comments

JSON array or object with `items`:

```json
[
  {
    "display_name": "用户A",
    "platform": "douyin",
    "source_type": "comment",
    "raw_text": "这个陪跑具体怎么收费？",
    "source_code": "ai-guide-douyin-short-003"
  }
]
```

CSV accepts the same column names. For imported comments, the engine sets
`needs_human_reply`; it must not enqueue an unsolicited DM.
