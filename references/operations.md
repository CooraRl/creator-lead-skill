# Operations Runbook

## Daily

1. Run `worker` with the production data directory.
2. Inspect failed outbox items and failed webhook deliveries.
3. Review new high-intent leads and assign a human owner.
4. Record status changes after actual human contact happens.
5. Check that the capture endpoint and `/health` are responding over HTTPS.

Do not send a second message merely to improve a daily activity metric.

## Production Schedule

The capture server must stay running. Run the worker on a short schedule, for
example every five minutes, so acknowledgements, alerts, nurture, and retries
continue without a person opening the CLI.

On Linux/macOS, use cron or a process manager:

```cron
*/5 * * * * cd /srv/creator-lead && /usr/bin/python3 scripts/creator_lead.py worker --config /etc/creator-lead/campaign.json --data-dir /var/lib/creator-lead --send >> /var/log/creator-lead-worker.log 2>&1
```

On Windows, create a Task Scheduler job that runs:

```text
python.exe C:\creator-lead\scripts\creator_lead.py worker --config C:\creator-lead\campaign.json --data-dir C:\creator-lead-data --send
```

Run it every five minutes under a dedicated service account. Restrict access to
the config, environment, and data directory. Test the exact task once with a
test mailbox before enabling the production job.

`assets/docker-compose.example.yml` runs the web service and the worker in
separate containers. From the repository root:

```text
cp assets/campaign.example.json campaign.json
cp assets/env.example .env
docker compose -f assets/docker-compose.example.yml up --build
```

The example binds the host port to `127.0.0.1:8787` only. The worker container
defaults to dry-run (no `--send`) so email and webhooks are not dispatched until
you explicitly change the command. A host webhook URL on loopback/private
addresses is rejected unless `CREATOR_LEAD_WEBHOOK_ALLOW_PRIVATE=1` (local
debug only). SMTP on port 587 uses STARTTLS unless you set
`CREATOR_LEAD_SMTP_STARTTLS=0` for a local test server.

`export` masks contact values and display names by default. Add `--include-pii`
only when writing to a protected path. `purge` is dry-run unless you pass
`--apply`; `--dry-run` is accepted as an explicit alias.

## Weekly

Run `report`. Review:

- submissions and unique leads;
- high/medium/low distribution;
- qualified-lead rate;
- booked-meeting rate and won rate;
- opt-out rate and delivery failures;
- qualified leads and bookings by `source_code`;
- time from submission to first human contact.

Pause a content angle when it generates traffic but no qualified behavior.
Rewrite the offer or landing page when traffic is meaningful but opt-in is
weak. Improve qualification when opt-in is healthy but sales rejects many
leads. Improve sales handoff when qualification is healthy but bookings are
weak.

## Experiment Cadence

Change one of these at a time:

- content hook or format;
- audience-specific promise;
- lead magnet;
- landing-page headline;
- consent/frequency wording;
- qualification rules;
- transactional acknowledgement;
- first sales follow-up script.

Use a decision window long enough to accumulate more than one or two leads.
Do not declare a winner from small samples or fabricated benchmark data.

## Incident Response

If the capture endpoint fails:

1. Put up a static fallback form owned by the same organization.
2. Export and reconcile submissions manually.
3. Do not silently discard requests.

If a message is sent to the wrong segment:

1. Stop the worker.
2. Identify every affected lead using outbox and event timestamps.
3. Send only a factual correction if needed.
4. Record the incident and require approval before resuming.

If a person asks not to be contacted:

1. Mark them `unsubscribed` immediately.
2. Cancel all pending outbox items.
3. Do not require an explanation or re-subscribe them later without a new
   affirmative opt-in.

## Retention

Set the shortest retention period that supports delivery, follow-up, and
accounting. Use `purge --dry-run` first to inspect expired records, then apply
the retention policy. Keep aggregate metrics that no longer identify a person.
