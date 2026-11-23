# Content Factory

The acquisition engine only works when qualified traffic enters the funnel.
Run content as a weekly production line with measurable source codes.

## Weekly Input

Start from one or more of these first-party or verifiable inputs:

- the creator's own analytics exports;
- a user-provided news JSON with source links;
- questions copied from comments with personal information removed;
- customer interview notes with permission to use anonymized themes;
- product usage data that cannot identify an individual.

Do not invent a trend, statistic, testimonial, or competitor claim.

## Production Stages

| Stage | Output | Gate |
| --- | --- | --- |
| 1. Signal selection | 3–7 themes tied to one audience problem | every theme has a source |
| 2. Promise design | one useful outcome per asset | outcome matches the landing-page offer |
| 3. Drafting | platform-native drafts | no fabricated claims or urgency |
| 4. Fact verification | source list and uncertain-claim markers | human resolves every `[待核对]` |
| 5. CTA linking | unique `src` code for every asset | link opens the correct campaign page |
| 6. Approval | publication-ready queue | named human approves |
| 7. Publication | real post URL/time | official platform only |
| 8. Measurement | views, clicks, leads, qualified leads | metrics imported from real sources |
| 9. Learning | keep/change/stop decision | conclusion relates to one test variable |

Use `content-plan` to turn a user-supplied news JSON into a ranked topic sheet:

```bash
python scripts/creator_lead.py content-plan \
  --config assets/campaign.example.json \
  --feed news.json \
  --output work/content-plan.md \
  --limit 5
```

The command assigns a stable source code and a tracking URL. It does not
publish.

## Three-Asset Batch

For each selected theme, generate only the formats the user needs:

- **Douyin:** 3-second observable problem, one useful explanation, one
  source-backed example, then the landing-page CTA.
- **X:** one claim per post, source links close to the claim, and a final CTA.
- **WeChat article:** clear promise, short sections, concrete checklist or
  example, and one repeated CTA.

Use the same campaign promise across formats, but rewrite the opening for the
platform's behavior. Do not copy the same paragraph everywhere.

## Attribution Rules

Every public asset receives one code:

```text
{campaign}-{platform}-{format}-{sequence}
```

The landing page stores this in `source_code`. The weekly report groups leads,
high-intent leads, qualified leads, bookings, and wins by this code.

Do not compare publishers using only views. Compare the cost and quality of
qualified conversations. If a source produces no qualified leads after a
reasonable sample, fix the audience promise or CTA before producing more of the
same content.

## Human Approval Checklist

- The source link opens and supports the exact claim.
- No numbers or customer stories were invented.
- The lead magnet exists and the delivery URL works.
- Consent wording matches the actual follow-up.
- The CTA uses the correct source code.
- The page works on mobile.
- The author is permitted to use every image, quote, and brand element.
- The published copy does not imply official platform endorsement.
