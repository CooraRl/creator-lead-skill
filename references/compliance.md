# Compliance and Safety Baseline

This is an engineering baseline, not legal advice. Check the current platform
terms, advertising rules, privacy law, and consent rules for the target market.

## Allowed by Default

- Generating and scheduling drafts for human review.
- Hosting an owned landing page that collects voluntarily submitted data.
- Explicit consent, deduplication, scoring, routing, webhook alerts, delivery
  messages, consented nurture, suppression, and reporting.
- Using documented official platform APIs that the account owner authorizes.

## Prohibited

- Buying or scraping contact lists.
- Logging into someone's account to crawl comments, followers, or private
  messages.
- Using browser automation or unofficial clients to send DMs, comments,
  follows, likes, or posts.
- Mass unsolicited messages, fake engagement, or fake scarcity.
- Sending marketing follow-up to someone who did not opt in.
- Publishing real names, emails, WeChat IDs, phone numbers, or message exports
  in the public repository.
- Storing passwords, cookies, tokens, API keys, or real `.env` files in the
  skill, config, database export, or Git history.
- Inventing testimonials, customer counts, conversion rates, revenue, or
  product capabilities.
- Inferring sensitive or protected traits for lead scoring.

## Required Controls

1. **Affirmative consent.** Unchecked by default; record version and time.
2. **Purpose limitation.** Explain resource delivery and follow-up separately.
3. **Minimization.** Collect only email or WeChat ID and relevant optional
   answers. Do not request phone numbers unless truly required.
4. **Data protection.** Serve the form over HTTPS. Restrict the data directory.
   Encrypt backups. Rotate leaked credentials.
5. **Retention.** Delete or anonymize person-level records at the configured
   deadline unless a documented obligation requires longer retention.
6. **Suppression.** Honor stop/unsubscribe requests immediately and cancel all
   pending outbox entries.
7. **Template governance.** Only pre-approved templates may be auto-sent.
8. **Human gate.** Public publication, sales promises, pricing exceptions,
   disputes, and personalized sensitive replies require human review.
9. **Auditability.** Preserve events and send records without storing
   unnecessary message content forever.
10. **Platform gate.** An integration is not allowed merely because it is
    technically possible. Confirm authorization and current policy first.

## Personal Information

The example follows a China-oriented privacy baseline because the original use
case covers Douyin and WeChat. In production, adapt notices and retention to the
actual jurisdictions and business. At minimum:

- identify the operator and contact route;
- state the data fields and purpose;
- state the retention period;
- explain sharing with CRM/email providers;
- provide a withdrawal/deletion route;
- obtain separate consent where local law requires it.

Do not use the existence of a consent checkbox to justify unrelated marketing.
