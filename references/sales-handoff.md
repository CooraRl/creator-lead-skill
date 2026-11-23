# Sales Handoff

Automation ends at a clean handoff. It should not manufacture urgency or send
unapproved sales promises.

## Priority Rules

- **High:** immediate private alert. A human reviews the source words and
  responds within the promised service window. Ask one useful clarifying
  question before proposing a meeting.
- **Medium:** deliver the resource, enter only the consented nurture path, and
  review after a meaningful behavior or reply.
- **Low:** deliver the promised asset if requested. Do not create a sales task
  without a new signal.
- **Unsubscribed:** cancel all pending messages and suppress future campaigns
  until a new, valid opt-in exists.

## First Human Response

Use the person's own words and include:

1. a direct acknowledgement;
2. one accurate statement about how you can help;
3. one qualifying question;
4. a clear next step;
5. an easy way to stop.

Do not send a price, guarantee, case study, or availability claim that is not
in the approved sales source of truth.

## Pipeline Truth

Update status only after the event happens:

- `contact_attempted`: a human sent a relevant response;
- `qualified`: fit and immediate need were confirmed;
- `meeting_booked`: both sides agreed to a time;
- `won`: payment or signed commitment exists;
- `lost`: the person declined or the opportunity was closed.

Opening the list or drafting a reply is not contact. A calendar click without a
confirmed booking is not a meeting.

## Owner SLA

Set one explicit service-level target, for example:

```text
High-intent human review within 4 business hours.
Integration failures reviewed twice per business day.
Weekly content decision every Friday.
```

Use the actual capacity of the business. If the SLA cannot be met, reduce
campaign volume before relaxing consent or increasing automated pressure.
