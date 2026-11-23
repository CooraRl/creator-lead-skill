#!/usr/bin/env python3
"""End-to-end smoke test for the creator-lead engine."""

from __future__ import annotations

import csv
import json
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import creator_lead as engine  # noqa: E402


def post(url: str, payload: dict[str, object], origin: str | None = None) -> tuple[int, dict[str, object]]:
    headers = {"Content-Type": "application/json"}
    if origin is not None:
        headers["Origin"] = origin
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body}
        return exc.code, parsed


def post_unsubscribe(url: str) -> int:
    request = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status


def token_from_outbox(db: engine.Database, lead_id: str) -> str:
    body = db.connection.execute(
        "SELECT body FROM outbox WHERE lead_id=? AND template='ack'",
        (lead_id,),
    ).fetchone()["body"]
    match = re.search(r"token=([A-Za-z0-9_-]+)", body)
    assert match, "ack mail is missing an unsubscribe token"
    return match.group(1)


def main() -> None:
    config = engine.load_config(ROOT / "assets" / "campaign.example.json")
    config["email"]["enabled"] = False
    config["campaign"]["public_base_url"] = "http://127.0.0.1"

    # Unit checks that do not need a server.
    try:
        engine.validate_webhook_url("http://127.0.0.1:8787/hook")
        raise AssertionError("loopback webhook should be rejected")
    except ValueError:
        pass
    try:
        engine.validate_webhook_url("file:///etc/passwd")
        raise AssertionError("file webhook should be rejected")
    except ValueError:
        pass
    engine.validate_webhook_url("http://127.0.0.1/hook", allow_private=True)

    with tempfile.TemporaryDirectory(prefix="creator-lead-smoke-") as tmp:
        db = engine.Database(Path(tmp))
        server = engine.CaptureServer(("127.0.0.1", 0), config, db)
        port = server.server_address[1]
        config["campaign"]["public_base_url"] = f"http://127.0.0.1:{port}"
        url = f"http://127.0.0.1:{port}/api/leads"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, _ = post(
                url,
                {
                    "email": "no-consent@example.com",
                    "consent": "",
                    "intent_text": "想咨询价格",
                },
            )
            assert status == 400, f"consent rejection returned {status}"

            status, result = post(
                url,
                {
                    "consent": "yes",
                    "intent_text": "想咨询报价和一对一方案",
                    "display_name": "无联系方式",
                },
            )
            assert status == 400, f"missing-contact landing submit returned {status}"

            status, result = post(
                url,
                {
                    "email": "csrf@example.com",
                    "consent": "yes",
                    "intent_text": "想领取资料",
                },
                origin="https://evil.example",
            )
            assert status == 403, f"cross-origin submit returned {status}"

            high_payload = {
                "email": "high@example.com",
                "display_name": "测试甲",
                "consent": "yes",
                "primary_goal": "团队培训",
                "intent_text": "想咨询报价和一对一方案",
                "source_code": "smoke-douyin-001",
                "utm_source": "douyin",
            }
            status, result = post(url, high_payload)
            assert status == 200 and result["duplicate"] is False

            status, result = post(url, high_payload)
            assert status == 200 and result["duplicate"] is True

            status, result = post(
                url,
                {
                    "email": "medium@example.com",
                    "display_name": "测试乙",
                    "consent": "yes",
                    "primary_goal": "提高工作效率",
                    "intent_text": "想领取资料和模板",
                    "source_code": "smoke-x-002",
                    "utm_source": "x",
                },
            )
            assert status == 200 and result["duplicate"] is False

            leads = db.connection.execute("SELECT * FROM leads ORDER BY created_at").fetchall()
            assert len(leads) == 2, f"expected 2 deduplicated leads, got {len(leads)}"
            by_email = {row["contact_value"]: row for row in leads}
            assert by_email["high@example.com"]["priority"] == "high"
            assert by_email["medium@example.com"]["priority"] == "medium"
            assert by_email["high@example.com"]["status"] == "new"
            assert by_email["medium@example.com"]["status"] == "nurturing"

            for row in leads:
                stored = row["unsubscribe_token"]
                assert re.fullmatch(r"[0-9a-f]{64}", stored), "unsubscribe token should be stored as a SHA-256 hex digest"

            ack_subjects = [
                row["subject"]
                for row in db.connection.execute("SELECT subject FROM outbox WHERE template='ack'").fetchall()
            ]
            assert len(ack_subjects) == 2
            assert all("《《" not in subject for subject in ack_subjects)

            medium = by_email["medium@example.com"]
            token = token_from_outbox(db, medium["id"])
            assert token != medium["unsubscribe_token"]
            unsubscribe_status = post_unsubscribe(
                f"http://127.0.0.1:{port}/unsubscribe?token={token}"
            )
            assert unsubscribe_status == 200
            updated_medium = db.connection.execute(
                "SELECT status FROM leads WHERE id=?",
                (medium["id"],),
            ).fetchone()
            assert updated_medium["status"] == "unsubscribed"
            cancelled = db.connection.execute(
                "SELECT COUNT(*) AS count FROM outbox WHERE lead_id=? AND status='cancelled'",
                (medium["id"],),
            ).fetchone()["count"]
            assert cancelled >= 1

            report = engine.report_data(config, db)
            assert report["leads"] == 2
            assert report["priorities"]["high"] == 1
            assert report["priorities"]["medium"] == 1
            assert report["rates"]["opt_out_count"] == 1

            export_path = Path(tmp) / "leads.csv"
            engine.export_leads(config, db, export_path, anonymize=False, include_pii=False)
            with export_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            contacts = {row["contact_value"] for row in rows}
            assert "high@example.com" not in contacts
            assert any("***@" in value for value in contacts)

            page = engine.landing_html(config, standalone=False)
            assert 'type="checkbox" name="consent"' in page
            assert "checked" not in page.split('name="consent"', 1)[1].split(">", 1)[0]
            print("Smoke test passed: consent, capture, dedupe, score, queue, unsubscribe, report, security checks.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            db.close()


if __name__ == "__main__":
    main()
