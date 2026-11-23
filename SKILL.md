---
name: creator-lead
description: Build and operate a compliant automated lead-acquisition system for creators, including content planning, a self-hosted lead-capture landing page, consent tracking, lead deduplication and scoring, CRM/webhook routing, email nurture, pipeline reporting, and experiment iteration. Use when the user wants an end-to-end automated customer-acquisition workflow or asks to upgrade an existing creator funnel.
---

# Creator Lead Automation

Turn a creator audience into a measurable, automated acquisition system:

```text
content attraction
  -> owned landing page
  -> explicit consent
  -> deduplication and scoring
  -> high-intent routing
  -> consented nurture
  -> sales handoff
  -> funnel report
  -> next content decision
```

The default implementation is an owned funnel. It may automatically collect,
qualify, notify, and nurture users who deliberately submit the lead form and
consent to follow-up. It must not use browser automation, scraped contact data,
mass unsolicited messages, or unofficial platform account control.

Before an external launch or any change to platform messaging, read
[compliance.md](references/compliance.md).

## Operating Modes

Choose the mode from what the user asks:

- **Build**: create or reconfigure a complete acquisition system. Use
  `references/operating-model.md`, then initialize the campaign.
- **Run**: execute daily or weekly operations, handle due leads, review reports,
  and decide the next content action. Use `references/operations.md`.
- **Integrate**: connect an approved channel, CRM, email service, or webhook.
  Read `references/channel-adapters.md`; implement only documented mechanisms
  the user is authorized to use.
- **Audit**: inspect an existing funnel for missing consent, duplicate capture,
  weak conversion, unsafe automation, or unmeasured stages. Report findings
  before changing external systems.

## End-to-End Build

1. Define the campaign contract. Capture a narrow audience, one painful
   problem, one concrete lead magnet, one primary conversion event, the sales
   offer, and the promised reply time. Ask only for missing information that
   materially changes the funnel.
2. Read [data-contract.md](references/data-contract.md). Adapt
   `assets/campaign.example.json` into the user's campaign configuration.
   Keep credentials in environment variables, never in the configuration.
3. Build the attraction layer. Produce platform-specific content with one
   clear CTA that points to the owned landing page or an approved official lead
   mechanism. Mark output as a draft until the user approves publication.
4. Build the conversion layer. Run `build-site` or `serve` to create the form,
   explicit consent checkbox, honeypot, delivery message, and privacy link.
   The landing page must state what the user will receive and how often they
   may be contacted.
5. Activate capture automation. `serve` stores submissions in SQLite,
   deduplicates by normalized contact, scores intent, records consent, routes
   high-intent leads, and queues only pre-approved follow-up.
6. Add delivery and routing. Configure an email sender or a private webhook.
   Verify in dry-run mode before sending. A failed downstream integration must
   never discard the captured lead.
7. Deploy behind HTTPS. Expose only `/`, `POST /api/leads`, and `/health`.
   Schedule `worker` frequently to send due messages and retry failures. Use
   `assets/docker-compose.example.yml` as a starting point when the user wants a
   containerized always-on deployment.
8. Run the operating loop. Review pipeline health daily and source/content
   performance weekly. Change one material variable per experiment.
9. Validate the handoff. Confirm that a lead can move from `new` to
   `qualified`, `meeting_booked`, `won`, `lost`, or `unsubscribed`, and that the
   events reconcile with the report.

Before launch, run the isolated acceptance test:

```bash
python scripts/smoke_test.py
```

## Commands

The bundled engine uses only the Python standard library.

```bash
python scripts/creator_lead.py init \
  --config assets/campaign.example.json \
  --data-dir .creator-lead-data

python scripts/creator_lead.py serve \
  --config assets/campaign.example.json \
  --data-dir .creator-lead-data \
  --host 127.0.0.1 --port 8787

python scripts/creator_lead.py ingest \
  --config assets/campaign.example.json \
  --data-dir .creator-lead-data \
  --file leads.json --platform douyin --source-type comment

python scripts/creator_lead.py list \
  --config assets/campaign.example.json \
  --data-dir .creator-lead-data \
  --priority high

python scripts/creator_lead.py worker \
  --config assets/campaign.example.json \
  --data-dir .creator-lead-data

python scripts/creator_lead.py report \
  --config assets/campaign.example.json \
  --data-dir .creator-lead-data
```

`worker` is dry-run by default. Add `--send` only after both sender
configuration and test delivery are verified. `build-site` exports a deployable
standalone page; its form posts to the configured public base URL.

## Automation Rules

- Capture only fields needed to deliver the promised resource and follow up.
- Require an affirmative consent action. Do not use a pre-checked checkbox.
- Deduplicate before scoring. Preserve the newest intent text and append an
  event rather than creating another customer record.
- Never infer sensitive traits or rank protected classes. Score only observable
  request intent, stated goal, source, and the user's own submitted words.
- Treat `高`/`high` as a sales-handoff signal, not permission for aggressive
  messaging.
- Keep the landing-page receipt and first message transactional. Put marketing
  follow-up behind opt-in.
- Respect unsubscribe immediately. Record it before suppressing future outbox
  items.
- If an integration is unavailable, use manual queue review instead of
  switching to unofficial automation.
- Do not claim autopilot before the live capture, routing, delivery, reporting,
  and unsubscribe paths have all been tested.

## Deliverables

For a complete build, hand off:

- campaign configuration with CTA and consent wording;
- landing page URL and deployment target;
- content calendar or first publishing batch;
- tested lead-capture endpoint;
- private CRM destination and high-intent alert;
- email/webhook delivery result;
- reported funnel baseline;
- owner, daily cadence, and next experiment.

See [operations.md](references/operations.md) for the runbook and metric
thresholds.
