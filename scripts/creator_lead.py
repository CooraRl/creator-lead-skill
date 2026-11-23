#!/usr/bin/env python3
"""Creator lead acquisition engine using only the Python standard library."""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import html
import ipaddress
import json
import os
import re
import secrets
import smtplib
import socket
import sqlite3
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable


UTC = timezone.utc
MAX_BODY_BYTES = 32_768
ALLOWED_STATUSES = {
    "new",
    "needs_human_reply",
    "nurturing",
    "qualified",
    "contact_attempted",
    "meeting_booked",
    "won",
    "lost",
    "unsubscribed",
}
ALLOWED_PRIORITIES = {"high", "medium", "low"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")



def hash_unsubscribe_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def look_up_lead_by_unsubscribe_token(db: "Database", token: str) -> sqlite3.Row | None:
    token = (token or "").strip()
    if not token or len(token) > 200:
        return None
    digest = hash_unsubscribe_token(token)
    rows = db.connection.execute(
        "SELECT * FROM leads WHERE unsubscribe_token IN (?, ?)",
        (digest, token),
    ).fetchall()
    for row in rows:
        stored = str(row["unsubscribe_token"])
        if len(stored) == len(digest) and hmac.compare_digest(stored, digest):
            return row
        if len(stored) == len(token) and hmac.compare_digest(stored, token):
            return row
    return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise urllib.error.HTTPError(newurl, code, "webhook redirects are not allowed", headers, fp)


def validate_webhook_url(url: str, *, allow_private: bool = False) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("webhook URL 只允许 http 或 https")
    host = parsed.hostname
    if not host:
        raise ValueError("webhook URL 缺少主机名")
    if allow_private:
        return url
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("无法解析 webhook 主机名") from exc
    if not infos:
        raise ValueError("无法解析 webhook 主机名")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ValueError("webhook URL 不能指向本机或内网地址")
    return url


def extract_unsubscribe_url(body: str) -> str:
    match = re.search(r"https?://\S+/unsubscribe\?token=[A-Za-z0-9_-]+", body)
    return match.group(0) if match else ""


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_json(stream: Any, value: Any) -> None:
    json.dump(value, stream, ensure_ascii=False, indent=2)
    stream.write("\n")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config(path: Path) -> dict[str, Any]:
    config = load_json(path)
    required = {
        "campaign",
        "offer",
        "capture",
        "scoring",
        "automation",
        "email",
        "webhook",
        "messages",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ValueError(f"配置文件缺少字段: {', '.join(missing)}")
    campaign_id = str(config["campaign"].get("id", "")).strip()
    if not campaign_id:
        raise ValueError("campaign.id 不能为空")
    if not str(config["campaign"].get("public_base_url", "")).startswith(("http://", "https://")):
        raise ValueError("campaign.public_base_url 必须是 http 或 https URL")
    if not str(config["offer"].get("delivery_url", "")).startswith(("http://", "https://")):
        raise ValueError("offer.delivery_url 必须是 http 或 https URL")
    if not config["capture"].get("consent_text"):
        raise ValueError("capture.consent_text 不能为空")
    return config


class Database:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "creator-lead.sqlite3"
        self.connection = sqlite3.connect(self.path, timeout=15)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA busy_timeout = 15000")
        self.initialize()
        try:
            os.chmod(self.data_dir, 0o700)
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source_channel TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_code TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                contact_type TEXT NOT NULL DEFAULT '',
                contact_value TEXT NOT NULL DEFAULT '',
                intent_text TEXT NOT NULL DEFAULT '',
                pain_point TEXT NOT NULL DEFAULT '',
                primary_goal TEXT NOT NULL DEFAULT '',
                consent_version TEXT NOT NULL DEFAULT '',
                consent_at TEXT,
                score INTEGER NOT NULL DEFAULT 0,
                priority TEXT NOT NULL,
                score_reasons TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL,
                owner TEXT NOT NULL DEFAULT '',
                next_action_at TEXT,
                retention_until TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                unsubscribe_token TEXT NOT NULL UNIQUE,
                UNIQUE(campaign_id, dedupe_key)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id TEXT PRIMARY KEY,
                lead_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                template TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                scheduled_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                sent_at TEXT,
                FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                UNIQUE(lead_id, channel, template)
            );
            CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority, status);
            CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source_code);
            CREATE INDEX IF NOT EXISTS idx_leads_retention ON leads(retention_until);
            CREATE INDEX IF NOT EXISTS idx_events_lead ON events(lead_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_outbox_due ON outbox(status, scheduled_at);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def clean_text(value: Any, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))
    return text.strip()[:limit]


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_wechat(value: str) -> str:
    return re.sub(r"\s+", "", value.strip()).lower()


def mask_contact(contact_type: str, value: str) -> str:
    if not value:
        return ""
    if contact_type == "email" and "@" in value:
        local, domain = value.split("@", 1)
        shown = local[:2] if len(local) > 2 else local[:1]
        return f"{shown}***@{domain}"
    if len(value) <= 3:
        return value[:1] + "**"
    return value[:2] + "***" + value[-1:]


def dedupe_key(campaign_id: str, contact_type: str, contact: str, platform: str, name: str, text: str) -> str:
    if contact:
        source = f"{campaign_id}|{contact_type}|{contact}"
    else:
        source = f"{campaign_id}|{platform}|{name}|{text}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def assess_intent(config: dict[str, Any], text: str, goal: str, source_type: str) -> tuple[int, str, list[str]]:
    scoring = config["scoring"]
    high_threshold = int(scoring.get("high_threshold", 60))
    medium_threshold = int(scoring.get("medium_threshold", 30))
    high_words = [str(word) for word in scoring.get("high_keywords", []) if str(word)]
    medium_words = [str(word) for word in scoring.get("medium_keywords", []) if str(word)]
    negative_words = [str(word) for word in scoring.get("negative_keywords", []) if str(word)]
    normalized = text.lower()
    high_hits = [word for word in high_words if word.lower() in normalized]
    medium_hits = [word for word in medium_words if word.lower() in normalized]
    negative_hits = [word for word in negative_words if word.lower() in normalized]
    goal_bonus = int(scoring.get("goal_bonus", {}).get(goal, 0) or 0)
    source_bonus = 5 if source_type == "landing_form" else 0
    reasons: list[str] = []

    if negative_hits:
        return 0, "low", [f"命中排除词: {', '.join(negative_hits[:3])}"]

    if high_hits:
        score = 55 + min(max(len(high_hits) - 1, 0) * 8, 16) + goal_bonus + source_bonus
        reasons.append(f"明确高意向词: {', '.join(high_hits[:4])}")
    elif medium_hits:
        score = 30 + min(len(medium_hits) * 6, 18) + goal_bonus + source_bonus
        # A download/learning request is medium by definition; only explicit
        # purchase, booking, or collaboration language may promote it to high.
        score = min(score, high_threshold - 1)
        reasons.append(f"资料或了解意向: {', '.join(medium_hits[:4])}")
    else:
        score = 5 + goal_bonus + source_bonus
        reasons.append("未命中明确意向词")

    if goal:
        reasons.append(f"目标: {goal}")
    if source_type == "landing_form":
        reasons.append("主动提交表单")
    score = max(0, min(score, 100))
    if score >= high_threshold:
        priority = "high"
    elif score >= medium_threshold:
        priority = "medium"
    else:
        priority = "low"
    return score, priority, reasons


@dataclass
class CreateResult:
    lead_id: str
    duplicate: bool
    priority: str
    score: int
    status: str


def render_template(value: str, **context: Any) -> str:
    safe_context = defaultdict(str)
    safe_context.update({key: str(val) for key, val in context.items()})
    try:
        return value.format_map(safe_context)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"消息模板格式错误: {exc}") from exc


def lead_template_context(
    config: dict[str, Any],
    lead: sqlite3.Row | dict[str, Any],
    *,
    unsubscribe_token: str = "",
) -> dict[str, str]:
    base_url = config["campaign"]["public_base_url"].rstrip("/")
    token = unsubscribe_token.strip()
    unsubscribe_url = f"{base_url}/unsubscribe?token={token}" if token else ""
    return {
        "display_name": lead["display_name"] or "你好",
        "offer_title": config["offer"]["title"],
        "promise": config["offer"]["promise"],
        "delivery_url": config["offer"]["delivery_url"],
        "delivery_instruction": config["offer"]["delivery_instruction"],
        "primary_goal": lead["primary_goal"] or "当前问题",
        "pain_point": lead["pain_point"] or "尚未填写",
        "campaign_name": config["campaign"]["name"],
        "unsubscribe_url": unsubscribe_url,
    }


def create_lead(
    db: Database,
    config: dict[str, Any],
    *,
    source_channel: str,
    source_type: str,
    source_code: str = "",
    display_name: str = "",
    contact_type: str = "",
    contact_value: str = "",
    intent_text: str = "",
    pain_point: str = "",
    primary_goal: str = "",
    consent_version: str = "",
    consent: bool = False,
    allow_automation: bool = True,
) -> CreateResult:
    now = utc_now()
    campaign_id = str(config["campaign"]["id"])
    source_channel = clean_text(source_channel, 40) or "manual"
    source_type = clean_text(source_type, 40) or "manual"
    source_code = clean_text(source_code, 100) or "direct"
    display_name = clean_text(display_name, 80)
    intent_text = clean_text(intent_text, 1200)
    pain_point = clean_text(pain_point, 1200)
    primary_goal = clean_text(primary_goal, 120)
    contact_type = clean_text(contact_type, 20).lower()
    contact_value = clean_text(contact_value, 254)
    if contact_type == "email":
        contact_value = normalize_email(contact_value)
        if contact_value and not EMAIL_RE.match(contact_value):
            raise ValueError("邮箱格式不正确")
    elif contact_type == "wechat":
        contact_value = normalize_wechat(contact_value)
    elif contact_value:
        raise ValueError("contact_type 只能是 email 或 wechat")

    if source_type == "landing_form" and not contact_value:
        raise ValueError("落地页提交必须填写邮箱或微信号")
    if not contact_value and not (display_name or intent_text):
        raise ValueError("至少需要联系方式、显示名或留言中的一项")

    consent_at = iso(now) if consent else None
    consent_version = clean_text(consent_version, 80) if consent else ""
    score, priority, reasons = assess_intent(
        config,
        f"{intent_text} {pain_point}",
        primary_goal,
        source_type,
    )
    if source_type == "landing_form":
        if contact_type == "wechat":
            status = "needs_human_reply"
        else:
            status = "new" if priority == "high" else "nurturing"
    else:
        status = "needs_human_reply"
    if priority == "low" and "命中排除词" in " ".join(reasons):
        status = "lost"
    next_action = now if priority == "high" else now + timedelta(days=1 if priority == "medium" else 3)
    retention_days = int(config.get("retention_days", 90))
    retention_until = now + timedelta(days=retention_days)
    dkey = dedupe_key(campaign_id, contact_type, contact_value, source_channel, display_name, intent_text)

    existing = db.connection.execute(
        "SELECT * FROM leads WHERE campaign_id = ? AND dedupe_key = ?",
        (campaign_id, dkey),
    ).fetchone()
    if existing:
        update_score = max(int(existing["score"]), score)
        update_priority = priority if score >= int(existing["score"]) else existing["priority"]
        update_status = existing["status"]
        if update_status != "unsubscribed" and status != "nurturing":
            update_status = status
        new_intent = intent_text or existing["intent_text"]
        new_pain = pain_point or existing["pain_point"]
        new_goal = primary_goal or existing["primary_goal"]
        new_consent_at = consent_at or existing["consent_at"]
        new_consent_version = consent_version or existing["consent_version"]
        db.connection.execute(
            """
            UPDATE leads
            SET updated_at=?, intent_text=?, pain_point=?, primary_goal=?, score=?,
                priority=?, score_reasons=?, status=?, consent_at=?, consent_version=?
            WHERE id=?
            """,
            (
                iso(now),
                new_intent,
                new_pain,
                new_goal,
                update_score,
                update_priority,
                json.dumps(reasons, ensure_ascii=False),
                update_status,
                new_consent_at,
                new_consent_version,
                existing["id"],
            ),
        )
        db.connection.execute(
            "INSERT INTO events(lead_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
            (existing["id"], "duplicate_merged", json.dumps({"source_channel": source_channel}, ensure_ascii=False), iso(now)),
        )
        db.connection.commit()
        return CreateResult(existing["id"], True, update_priority, update_score, update_status)

    lead_id = str(uuid.uuid4())
    raw_unsubscribe_token = secrets.token_urlsafe(24)
    unsubscribe_token = hash_unsubscribe_token(raw_unsubscribe_token)
    db.connection.execute(
        """
        INSERT INTO leads (
            id, campaign_id, created_at, updated_at, source_channel, source_type,
            source_code, display_name, contact_type, contact_value, intent_text,
            pain_point, primary_goal, consent_version, consent_at, score, priority,
            score_reasons, status, owner, next_action_at, retention_until,
            dedupe_key, unsubscribe_token
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            campaign_id,
            iso(now),
            iso(now),
            source_channel,
            source_type,
            source_code,
            display_name,
            contact_type,
            contact_value,
            intent_text,
            pain_point,
            primary_goal,
            consent_version,
            consent_at,
            score,
            priority,
            json.dumps(reasons, ensure_ascii=False),
            status,
            "",
            iso(next_action),
            iso(retention_until),
            dkey,
            unsubscribe_token,
        ),
    )
    db.connection.execute(
        "INSERT INTO events(lead_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
        (
            lead_id,
            "lead_created",
            json.dumps({"score": score, "priority": priority, "source_code": source_code}, ensure_ascii=False),
            iso(now),
        ),
    )
    lead = db.connection.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    assert lead is not None

    automation_enabled = bool(config["automation"].get("enabled", True))
    if allow_automation and automation_enabled and source_type == "landing_form" and consent_at and contact_type == "email":
        if config["automation"].get("acknowledgement", True):
            enqueue_email(db, config, lead, "ack", now, unsubscribe_token=raw_unsubscribe_token)
        if priority != "high":
            for item in config["automation"].get("nurture", []):
                enqueue_email(
                    db,
                    config,
                    lead,
                    str(item["template"]),
                    now + timedelta(hours=int(item["delay_hours"])),
                    sequence=int(item["sequence"]),
                    unsubscribe_token=raw_unsubscribe_token,
                )

    if (
        allow_automation
        and automation_enabled
        and priority == "high"
        and config["automation"].get("high_intent_alert", True)
        and config["webhook"].get("enabled", False)
    ):
        enqueue_webhook(db, config, lead, now)
    if (
        allow_automation
        and automation_enabled
        and source_type == "landing_form"
        and contact_type == "wechat"
        and config["webhook"].get("enabled", False)
    ):
        enqueue_webhook(db, config, lead, now)

    db.connection.commit()
    return CreateResult(lead_id, False, priority, score, status)


def enqueue_email(
    db: Database,
    config: dict[str, Any],
    lead: sqlite3.Row,
    template_name: str,
    scheduled_at: datetime,
    *,
    sequence: int = 0,
    unsubscribe_token: str = "",
) -> None:
    template_key = "ack" if template_name == "ack" else template_name
    subject_key = "ack_subject" if template_key == "ack" else f"{template_key}_subject"
    body_key = "ack_body" if template_key == "ack" else f"{template_key}_body"
    messages = config["messages"]
    if subject_key not in messages or body_key not in messages:
        raise ValueError(f"缺少消息模板: {subject_key} / {body_key}")
    context = lead_template_context(config, lead, unsubscribe_token=unsubscribe_token)
    subject = render_template(str(messages[subject_key]), **context)
    body = render_template(str(messages[body_key]), **context)
    if context["unsubscribe_url"] not in body:
        body += f"\n\n退订: {context['unsubscribe_url']}\n"
    stored_template = template_key if not sequence else f"{template_key}_{sequence}"
    db.connection.execute(
        """
        INSERT OR IGNORE INTO outbox (
            id, lead_id, channel, template, subject, body, scheduled_at,
            status, attempts, last_error, created_at
        ) VALUES (?, ?, 'email', ?, ?, ?, ?, 'pending', 0, '', ?)
        """,
        (
            str(uuid.uuid4()),
            lead["id"],
            stored_template,
            subject,
            body,
            iso(scheduled_at),
            iso(utc_now()),
        ),
    )


def enqueue_webhook(db: Database, config: dict[str, Any], lead: sqlite3.Row, scheduled_at: datetime) -> None:
    is_high_intent = lead["priority"] == "high"
    payload = {
        "event": "creator_lead.high_intent" if is_high_intent else "creator_lead.wechat_handoff",
        "campaign_id": config["campaign"]["id"],
        "campaign_name": config["campaign"]["name"],
        "lead_id": lead["id"],
        "priority": lead["priority"],
        "score": lead["score"],
        "source_channel": lead["source_channel"],
        "source_code": lead["source_code"],
        "display_name": lead["display_name"],
        "contact_type": lead["contact_type"],
        "contact_value": lead["contact_value"],
        "primary_goal": lead["primary_goal"],
        "intent_text": lead["intent_text"],
        "created_at": lead["created_at"],
    }
    db.connection.execute(
        """
        INSERT OR IGNORE INTO outbox (
            id, lead_id, channel, template, subject, body, scheduled_at,
            status, attempts, last_error, created_at
        ) VALUES (?, ?, 'webhook', ?, '', ?, ?, 'pending', 0, '', ?)
        """,
        (
            str(uuid.uuid4()),
            lead["id"],
            "high_intent_alert" if is_high_intent else "wechat_handoff",
            json.dumps(payload, ensure_ascii=False),
            iso(scheduled_at),
            iso(utc_now()),
        ),
    )


def update_lead_status(db: Database, lead_id: str, status: str, owner: str = "", note: str = "") -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"不支持的状态: {status}")
    lead = db.connection.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead:
        raise ValueError("未找到该线索")
    now = iso(utc_now())
    fields = ["status = ?", "updated_at = ?"]
    values: list[Any] = [status, now]
    if owner:
        fields.append("owner = ?")
        values.append(clean_text(owner, 100))
    if status == "unsubscribed":
        fields.append("next_action_at = NULL")
        db.connection.execute(
            "UPDATE outbox SET status = 'cancelled' WHERE lead_id = ? AND status IN ('pending', 'failed')",
            (lead_id,),
        )
    elif status in {"meeting_booked", "won", "lost"}:
        db.connection.execute(
            """
            UPDATE outbox SET status = 'cancelled'
            WHERE lead_id = ? AND status IN ('pending', 'failed')
              AND template LIKE 'nurture_%'
            """,
            (lead_id,),
        )
    values.append(lead_id)
    db.connection.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ?", values)
    db.connection.execute(
        "INSERT INTO events(lead_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
        (
            lead_id,
            "status_changed",
            json.dumps({"from": lead["status"], "to": status, "note": clean_text(note, 1000)}, ensure_ascii=False),
            now,
        ),
    )
    db.connection.commit()


def mark_unsubscribed(db: Database, token: str) -> bool:
    lead = look_up_lead_by_unsubscribe_token(db, token)
    if not lead:
        return False
    update_lead_status(db, lead["id"], "unsubscribed", note="one-click unsubscribe")
    return True


def import_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    data = load_json(path)
    if isinstance(data, dict):
        items = data.get("items", [])
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("导入文件必须是 JSON 数组、带 items 的对象或 CSV")
    if not isinstance(items, list):
        raise ValueError("items 必须是数组")
    return [dict(item) for item in items if isinstance(item, dict)]


def parse_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "是"}


def landing_html(config: dict[str, Any], *, standalone: bool) -> str:
    campaign = config["campaign"]
    offer = config["offer"]
    capture = config["capture"]
    goals = list(config["scoring"].get("goal_bonus", {}).keys())
    if "只是想先看看" not in goals:
        goals.append("只是想先看看")
    goal_options = "\n".join(
        f'<option value="{html.escape(goal, quote=True)}">{html.escape(goal)}</option>' for goal in goals
    )
    api_url = f"{campaign['public_base_url'].rstrip('/')}/api/leads" if standalone else "/api/leads"
    title = html.escape(offer["title"])
    campaign_name = html.escape(campaign["name"])
    promise = html.escape(offer["promise"])
    consent_text = html.escape(capture["consent_text"])
    privacy_url = html.escape(capture["privacy_url"], quote=True)
    success_message = html.escape(capture["success_message"])
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | {campaign_name}</title>
  <meta name="description" content="{promise}">
  <style>
    :root {{
      color-scheme: light;
      --ink: #102a2a;
      --muted: #476565;
      --paper: #f5f1e8;
      --card: #fffdf8;
      --accent: #0f766e;
      --accent-dark: #0a4f4a;
      --line: #c9d6d2;
      --warn: #9f2d2d;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 10%, #dcefe6 0, transparent 35%),
        linear-gradient(145deg, var(--paper), #e7ece7);
      font-family: "Noto Sans SC", "Microsoft YaHei", system-ui, sans-serif;
    }}
    main {{
      width: min(1080px, calc(100% - 32px));
      margin: 0 auto;
      padding: 64px 0;
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 56px;
      align-items: start;
    }}
    .eyebrow {{ color: var(--accent); font-weight: 800; letter-spacing: .12em; }}
    h1 {{ font-size: clamp(2.4rem, 5vw, 4.6rem); line-height: .98; margin: 18px 0 24px; }}
    .promise {{ color: var(--muted); font-size: 1.15rem; line-height: 1.8; max-width: 36rem; }}
    .points {{ margin: 32px 0 0; padding: 0; list-style: none; }}
    .points li {{ margin: 14px 0; padding-left: 28px; position: relative; }}
    .points li::before {{
      content: ""; width: 12px; height: 12px; border-radius: 50%;
      background: var(--accent); position: absolute; left: 2px; top: .42em;
      box-shadow: 0 0 0 5px #d2e7df;
    }}
    .card {{
      background: var(--card); border: 1px solid var(--line); border-radius: 24px;
      padding: 28px; box-shadow: 0 24px 70px rgba(24, 61, 57, .12);
    }}
    label {{ display: block; font-weight: 700; margin: 16px 0 7px; }}
    input, select, textarea {{
      width: 100%; border: 1px solid var(--line); border-radius: 12px;
      padding: 12px 14px; font: inherit; color: var(--ink); background: white;
    }}
    textarea {{ min-height: 96px; resize: vertical; }}
    input:focus, select:focus, textarea:focus {{
      outline: 3px solid #bfe1d6; border-color: var(--accent);
    }}
    .consent {{ display: flex; gap: 10px; align-items: flex-start; margin: 18px 0; font-size: .92rem; color: var(--muted); }}
    .consent input {{ width: auto; margin-top: 3px; }}
    button {{
      width: 100%; border: 0; border-radius: 999px; padding: 15px 20px;
      background: var(--accent); color: white; font: inherit; font-weight: 800;
      cursor: pointer; margin-top: 6px;
    }}
    button:hover {{ background: var(--accent-dark); }}
    button:disabled {{ opacity: .6; cursor: wait; }}
    .fine {{ font-size: .78rem; color: var(--muted); line-height: 1.6; }}
    .error {{ color: var(--warn); min-height: 1.5em; margin: 12px 0; }}
    .success {{ display: none; background: #e4f4ed; border: 1px solid #aad5c2; padding: 16px; border-radius: 14px; margin-top: 16px; }}
    .honeypot {{ position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }}
    @media (max-width: 800px) {{
      main {{ grid-template-columns: 1fr; gap: 32px; padding: 36px 0; }}
      h1 {{ font-size: clamp(2.4rem, 13vw, 4rem); }}
    }}
  </style>
</head>
<body>
  <main>
    <section>
      <div class="eyebrow">为实际工作解决问题的入门资料</div>
      <h1>{title}</h1>
      <p class="promise">{promise}</p>
      <ul class="points">
        <li>先完成一个真实任务，不做空泛收藏</li>
        <li>提交后立即进入资料交付流程</li>
        <li>只收集交付和跟进所需的最少信息</li>
      </ul>
    </section>
    <section class="card" aria-labelledby="form-title">
      <h2 id="form-title">领取资料</h2>
      <p class="fine">填写邮箱或微信号中的至少一项。邮箱用于自动发送资料，微信号用于人工跟进。</p>
      <form id="lead-form" novalidate>
        <label for="display_name">怎么称呼你</label>
        <input id="display_name" name="display_name" maxlength="80" autocomplete="name" placeholder="可选">

        <label for="email">邮箱</label>
        <input id="email" name="email" type="email" maxlength="254" autocomplete="email" placeholder="name@example.com">

        <label for="wechat">微信号</label>
        <input id="wechat" name="wechat" maxlength="64" placeholder="可选；没有邮箱时请填写">

        <label for="primary_goal">你现在最想解决什么</label>
        <select id="primary_goal" name="primary_goal">{goal_options}</select>

        <label for="intent_text">补充一句具体情况</label>
        <textarea id="intent_text" name="intent_text" maxlength="1000" placeholder="例如：想知道团队培训怎么开始"></textarea>

        <div class="honeypot" aria-hidden="true">
          <label for="website">Website</label>
          <input id="website" name="website" tabindex="-1" autocomplete="off">
        </div>
        <input type="hidden" name="source_code" id="source_code" value="direct">
        <input type="hidden" name="utm_source" id="utm_source">
        <input type="hidden" name="utm_medium" id="utm_medium">
        <input type="hidden" name="utm_campaign" id="utm_campaign">

        <label class="consent">
          <input type="checkbox" name="consent" value="yes">
          <span>{consent_text} <a href="{privacy_url}" rel="noopener">隐私说明</a></span>
        </label>
        <div id="form-error" class="error" role="alert"></div>
        <button id="submit-btn" type="submit">发送资料</button>
      </form>
      <div id="success" class="success" role="status">{success_message}</div>
      <p class="fine">请只提交你愿意用于接收资料和跟进的信息。不要填写身份证、银行卡、密码等敏感数据。</p>
    </section>
  </main>
  <script>
    const params = new URLSearchParams(window.location.search);
    for (const key of ["utm_source", "utm_medium", "utm_campaign"]) {{
      const el = document.getElementById(key);
      if (el && params.get(key)) el.value = params.get(key);
    }}
    const source = document.getElementById("source_code");
    if (source) source.value = params.get("src") || params.get("utm_source") || "direct";
    const form = document.getElementById("lead-form");
    const button = document.getElementById("submit-btn");
    const errorBox = document.getElementById("form-error");
    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      errorBox.textContent = "";
      const data = Object.fromEntries(new FormData(form).entries());
      if (!data.consent) {{
        errorBox.textContent = "请先勾选同意接收资料和跟进。";
        return;
      }}
      if (!data.email.trim() && !data.wechat.trim()) {{
        errorBox.textContent = "请填写邮箱或微信号中的至少一项。";
        return;
      }}
      button.disabled = true;
      button.textContent = "正在提交…";
      try {{
        const response = await fetch({json.dumps(api_url)}, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(data)
        }});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "提交失败，请稍后重试。");
        form.style.display = "none";
        document.getElementById("success").style.display = "block";
      }} catch (error) {{
        errorBox.textContent = error.message || "网络异常，请稍后重试。";
        button.disabled = false;
        button.textContent = "重新提交";
      }}
    }});
  </script>
</body>
</html>
"""


def build_site(config: dict[str, Any], output: Path, *, force: bool = False) -> Path:
    output = output.resolve()
    if output.exists() and not force:
        raise ValueError(f"目标已存在: {output}；如需覆盖请加 --force")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(landing_html(config, standalone=True), encoding="utf-8")
    return output


class RateLimiter:
    def __init__(self, limit: int = 8, window_seconds: int = 600) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.events: dict[str, list[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            recent = [stamp for stamp in self.events[key] if now - stamp < self.window_seconds]
            if len(recent) >= self.limit:
                self.events[key] = recent
                return False
            recent.append(now)
            self.events[key] = recent
            if len(self.events) > 4096:
                stale = [item for item, stamps in self.events.items() if not stamps or now - stamps[-1] >= self.window_seconds]
                for item in stale:
                    self.events.pop(item, None)
            return True


class CaptureServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], config: dict[str, Any], db: Database) -> None:
        super().__init__(address, LeadRequestHandler)
        self.config = config
        self.db = db
        self.limiter = RateLimiter(limit=int(config["capture"].get("rate_limit_per_10m", 20)))


class LeadRequestHandler(BaseHTTPRequestHandler):
    server: CaptureServer
    server_version = "CreatorLead/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        message = fmt % args
        message = re.sub(r"(token=)[^&\s\"]+", r"\1[redacted]", message)
        sys.stderr.write("%s - %s\n" % (self.address_string(), message))

    def origin_allowed(self) -> bool:
        base = urllib.parse.urlparse(str(self.server.config["campaign"]["public_base_url"]))
        origin = self.headers.get("Origin", "").strip()
        referer = self.headers.get("Referer", "").strip()

        def same_origin(url: str) -> bool:
            parsed = urllib.parse.urlparse(url)
            return bool(parsed.scheme and parsed.netloc) and (parsed.scheme, parsed.netloc) == (base.scheme, base.netloc)

        if origin:
            return same_origin(origin)
        if referer:
            return same_origin(referer)
        return True

    def security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "connect-src 'self' https: http://127.0.0.1:*; frame-ancestors 'none'",
        )

    def send_bytes(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.security_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_bytes(status, "application/json; charset=utf-8", body)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/":
            body = landing_html(self.server.config, standalone=False).encode("utf-8")
            self.send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", body)
            return
        if parsed.path == "/health":
            self.send_json(HTTPStatus.OK, {"ok": True, "campaign": self.server.config["campaign"]["id"]})
            return
        if parsed.path == "/unsubscribe":
            token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
            message = "请点击下方按钮确认退订。"
            page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>退订</title><body style="font-family:system-ui;padding:48px;max-width:680px">
            <h1>退订</h1><p>{html.escape(message)}</p>
            <form method="post" action="/unsubscribe?token={html.escape(urllib.parse.quote(token), quote=True)}">
            <button type="submit" style="padding:12px 20px">确认停止接收</button></form>
            </body></html>"""
            self.send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", page.encode("utf-8"))
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/unsubscribe":
            token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0]
            db = Database(self.server.db.data_dir)
            try:
                success = mark_unsubscribed(db, token) if token else False
            finally:
                db.close()
            message = "你已停止接收后续邮件。" if success else "退订链接无效或已过期。"
            page = f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>退订</title><body style="font-family:system-ui;padding:48px;max-width:680px">
            <h1>退订</h1><p>{html.escape(message)}</p></body></html>"""
            self.send_bytes(HTTPStatus.OK, "text/html; charset=utf-8", page.encode("utf-8"))
            return
        if parsed.path != "/api/leads":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        if not self.origin_allowed():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "来源不被允许"})
            return
        if self.server.config["capture"].get("trust_proxy_headers", False):
            client = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip() or self.client_address[0]
        else:
            client = self.client_address[0]
        if not self.server.limiter.allow(client):
            self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "提交过于频繁，请稍后再试。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "请求长度无效"})
            return
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "请求内容为空或过大"})
            return
        raw_body = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        try:
            if content_type == "application/json":
                payload = json.loads(raw_body.decode("utf-8"))
            elif content_type == "application/x-www-form-urlencoded":
                payload = {key: values[-1] for key, values in urllib.parse.parse_qs(raw_body.decode("utf-8")).items()}
            else:
                raise ValueError("Content-Type 必须是 application/json 或 application/x-www-form-urlencoded")
            if not isinstance(payload, dict):
                raise ValueError("请求体必须是对象")
            if clean_text(payload.get("website"), 10):
                self.send_json(HTTPStatus.OK, {"ok": True, "message": self.server.config["capture"]["success_message"]})
                return
            email = clean_text(payload.get("email"), 254)
            wechat = clean_text(payload.get("wechat"), 64)
            contact_type = "email" if email else ("wechat" if wechat else "")
            contact_value = email if email else wechat
            if not parse_truthy(payload.get("consent")):
                raise ValueError("必须明确同意后才能提交")
            db = Database(self.server.db.data_dir)
            try:
                result = create_lead(
                    db,
                    self.server.config,
                    source_channel=clean_text(payload.get("utm_source"), 40) or "owned-site",
                    source_type="landing_form",
                    source_code=clean_text(payload.get("source_code"), 100) or "direct",
                    display_name=clean_text(payload.get("display_name"), 80),
                    contact_type=contact_type,
                    contact_value=contact_value,
                    intent_text=clean_text(payload.get("intent_text"), 1200),
                    pain_point=clean_text(payload.get("pain_point"), 1200),
                    primary_goal=clean_text(payload.get("primary_goal"), 120),
                    consent_version=clean_text(self.server.config["capture"].get("consent_version"), 80),
                    consent=True,
                    allow_automation=True,
                )
            finally:
                db.close()
            self.send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "message": self.server.config["capture"]["success_message"],
                    "duplicate": result.duplicate,
                },
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except sqlite3.Error:
            traceback.print_exc()
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "暂时无法保存，请稍后重试。"})


def send_email(config: dict[str, Any], lead: sqlite3.Row, subject: str, body: str) -> None:
    email_cfg = config["email"]
    if not email_cfg.get("enabled", False):
        raise RuntimeError("email.enabled 未开启")
    host = os.environ.get(str(email_cfg.get("host_env", "CREATOR_LEAD_SMTP_HOST")), "")
    port_text = os.environ.get(str(email_cfg.get("port_env", "CREATOR_LEAD_SMTP_PORT")), "587")
    user = os.environ.get(str(email_cfg.get("user_env", "CREATOR_LEAD_SMTP_USER")), "")
    password = os.environ.get(str(email_cfg.get("password_env", "CREATOR_LEAD_SMTP_PASSWORD")), "")
    from_address = os.environ.get(str(email_cfg.get("from_env", "CREATOR_LEAD_SMTP_FROM")), "")
    if not host or not from_address:
        raise RuntimeError("缺少 SMTP_HOST 或 SMTP_FROM")
    if not lead["contact_value"]:
        raise RuntimeError("该线索没有邮箱")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_address
    message["To"] = lead["contact_value"]
    unsubscribe_url = extract_unsubscribe_url(body)
    if unsubscribe_url:
        message["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(body)
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT 不是有效端口") from exc
    if port == 465:
        smtp = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        smtp = smtplib.SMTP(host, port, timeout=20)
    with smtp:
        smtp.ehlo()
        starttls_flag = os.environ.get("CREATOR_LEAD_SMTP_STARTTLS", "").strip().lower()
        use_starttls = port not in {25, 465}
        if starttls_flag in {"0", "false", "no", "off"}:
            use_starttls = False
        elif starttls_flag in {"1", "true", "yes", "on"}:
            use_starttls = True
        if use_starttls:
            smtp.starttls()
            smtp.ehlo()
        if user:
            smtp.login(user, password)
        smtp.send_message(message)


def send_webhook(config: dict[str, Any], body: str) -> None:
    url = os.environ.get(str(config["webhook"].get("url_env", "CREATOR_LEAD_WEBHOOK_URL")), "")
    if not config["webhook"].get("enabled", False):
        raise RuntimeError("webhook.enabled 未开启")
    if not url:
        raise RuntimeError("缺少 webhook URL 环境变量")
    allow_private = str(os.environ.get("CREATOR_LEAD_WEBHOOK_ALLOW_PRIVATE", "")).strip().lower() in {"1", "true", "yes"}
    if config["webhook"].get("allow_private"):
        allow_private = True
    try:
        validate_webhook_url(url, allow_private=allow_private)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    request = urllib.request.Request(
        url,
        data=body.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "CreatorLead/1.0"},
    )
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"webhook HTTP {response.status}")


def run_worker(config: dict[str, Any], db: Database, *, send: bool, limit: int) -> int:
    now = iso(utc_now())
    rows = db.connection.execute(
        """
        SELECT o.*, l.contact_type, l.contact_value, l.display_name, l.primary_goal,
               l.pain_point, l.unsubscribe_token, l.status AS lead_status
        FROM outbox o JOIN leads l ON l.id = o.lead_id
        WHERE o.status IN ('pending', 'failed') AND o.scheduled_at <= ?
          AND o.attempts < 3
        ORDER BY o.scheduled_at ASC LIMIT ?
        """,
        (now, limit),
    ).fetchall()
    if not rows:
        print("没有到期消息。")
        return 0
    print(f"到期消息: {len(rows)}")
    for item in rows:
        print(f"- {item['channel']} | {item['template']} | lead={item['lead_id']} | scheduled={item['scheduled_at']}")
        if not send:
            if item["channel"] == "email":
                print(f"  subject={item['subject']}")
            continue
        if item["lead_status"] == "unsubscribed":
            db.connection.execute("UPDATE outbox SET status='cancelled' WHERE id=?", (item["id"],))
            db.connection.commit()
            print("  已取消：用户已退订")
            continue
        try:
            if item["channel"] == "email":
                send_email(config, item, item["subject"], item["body"])
            elif item["channel"] == "webhook":
                send_webhook(config, item["body"])
            else:
                raise RuntimeError(f"不支持的外发渠道: {item['channel']}")
            db.connection.execute(
                "UPDATE outbox SET status='sent', attempts=attempts+1, sent_at=?, last_error='' WHERE id=?",
                (iso(utc_now()), item["id"]),
            )
            print("  已发送")
        except Exception as exc:  # keep the lead and surface the exact integration failure
            attempts = int(item["attempts"]) + 1
            status = "failed" if attempts >= 3 else "pending"
            retry_at = utc_now() + timedelta(minutes=15 * attempts)
            db.connection.execute(
                "UPDATE outbox SET status=?, attempts=?, last_error=?, scheduled_at=? WHERE id=?",
                (status, attempts, clean_text(exc, 500), iso(retry_at), item["id"]),
            )
            print(f"  失败：{exc}")
        db.connection.commit()
    return len(rows)


def lead_to_dict(row: sqlite3.Row, *, show_contact: bool = False) -> dict[str, Any]:
    item = dict(row)
    item.pop("unsubscribe_token", None)
    if not show_contact:
        item["contact_value"] = mask_contact(item["contact_type"], item["contact_value"])
    try:
        item["score_reasons"] = json.loads(item["score_reasons"])
    except (TypeError, json.JSONDecodeError):
        pass
    return item


def print_table(rows: Iterable[sqlite3.Row], show_contact: bool = False) -> None:
    rows = list(rows)
    if not rows:
        print("没有符合条件的线索。")
        return
    print("id\tpriority\tscore\tstatus\tsource_code\tcontact\tgoal\tnext_action")
    for row in rows:
        print(
            "\t".join(
                [
                    str(row["id"]),
                    str(row["priority"]),
                    str(row["score"]),
                    str(row["status"]),
                    str(row["source_code"]),
                    mask_contact(row["contact_type"], row["contact_value"]) if not show_contact else row["contact_value"],
                    str(row["primary_goal"]),
                    str(row["next_action_at"] or ""),
                ]
            )
        )


def report_data(config: dict[str, Any], db: Database) -> dict[str, Any]:
    campaign_id = config["campaign"]["id"]
    leads = db.connection.execute("SELECT * FROM leads WHERE campaign_id = ?", (campaign_id,)).fetchall()
    priorities = Counter(row["priority"] for row in leads)
    statuses = Counter(row["status"] for row in leads)
    sources: dict[str, Counter[str]] = defaultdict(Counter)
    for row in leads:
        source = row["source_code"] or "direct"
        sources[source]["leads"] += 1
        if row["priority"] == "high":
            sources[source]["high"] += 1
        if row["status"] in {"qualified", "contact_attempted", "meeting_booked", "won"}:
            sources[source]["qualified"] += 1
        if row["status"] == "meeting_booked":
            sources[source]["booked"] += 1
        if row["status"] == "won":
            sources[source]["won"] += 1
    outbox = Counter(
        row["status"]
        for row in db.connection.execute(
            """
            SELECT o.status FROM outbox o JOIN leads l ON l.id=o.lead_id
            WHERE l.campaign_id=?
            """,
            (campaign_id,),
        ).fetchall()
    )
    total = len(leads)
    consented = sum(1 for row in leads if row["consent_at"])
    qualified = sum(statuses[key] for key in ("qualified", "contact_attempted", "meeting_booked", "won"))
    booked = statuses["meeting_booked"] + statuses["won"]
    won = statuses["won"]
    return {
        "campaign_id": campaign_id,
        "generated_at": iso(utc_now()),
        "leads": total,
        "consented": consented,
        "priorities": {key: priorities[key] for key in sorted(ALLOWED_PRIORITIES)},
        "statuses": dict(sorted(statuses.items())),
        "outbox": dict(sorted(outbox.items())),
        "rates": {
            "consent_rate": round(consented / total, 4) if total else 0,
            "qualified_rate": round(qualified / total, 4) if total else 0,
            "booked_rate": round(booked / total, 4) if total else 0,
            "won_rate": round(won / total, 4) if total else 0,
            "opt_out_count": statuses["unsubscribed"],
        },
        "sources": {source: dict(counter) for source, counter in sorted(sources.items())},
    }


def print_report(report: dict[str, Any]) -> None:
    print(f"Campaign: {report['campaign_id']}")
    print(f"线索: {report['leads']} | 明确同意: {report['consented']}")
    print(
        "优先级: high={high} medium={medium} low={low}".format(
            **report["priorities"],
        )
    )
    print("状态: " + (", ".join(f"{k}={v}" for k, v in report["statuses"].items()) or "暂无"))
    print("发件箱: " + (", ".join(f"{k}={v}" for k, v in report["outbox"].items()) or "暂无"))
    rates = report["rates"]
    print(
        "转化: consent={consent_rate:.1%} qualified={qualified_rate:.1%} "
        "booked={booked_rate:.1%} won={won_rate:.1%}".format(**rates)
    )


def export_leads(config: dict[str, Any], db: Database, output: Path, *, anonymize: bool, include_pii: bool = False) -> int:
    if include_pii and anonymize:
        raise ValueError("不能同时使用 --anonymize 和 --include-pii")
    rows = db.connection.execute(
        "SELECT * FROM leads WHERE campaign_id = ? ORDER BY created_at DESC",
        (config["campaign"]["id"],),
    ).fetchall()
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "created_at",
        "updated_at",
        "source_channel",
        "source_type",
        "source_code",
        "display_name",
        "contact_type",
        "contact_value",
        "intent_text",
        "pain_point",
        "primary_goal",
        "consent_version",
        "consent_at",
        "score",
        "priority",
        "score_reasons",
        "status",
        "owner",
        "next_action_at",
        "retention_until",
    ]
    temp = output.with_suffix(output.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            item = {key: row[key] for key in fieldnames}
            if anonymize:
                item["display_name"] = ""
                item["contact_value"] = ""
                item["intent_text"] = ""
                item["pain_point"] = ""
                item["score_reasons"] = "[]"
                item["owner"] = ""
            elif not include_pii:
                item["contact_value"] = mask_contact(row["contact_type"], row["contact_value"])
                item["display_name"] = (row["display_name"][:1] + "***") if row["display_name"] else ""
            writer.writerow(item)
    temp.replace(output)
    return len(rows)


def purge_leads(db: Database, config: dict[str, Any], *, apply: bool) -> int:
    now = iso(utc_now())
    rows = db.connection.execute(
        "SELECT id FROM leads WHERE campaign_id=? AND retention_until <= ?",
        (config["campaign"]["id"], now),
    ).fetchall()
    if apply and rows:
        db.connection.executemany("DELETE FROM leads WHERE id=?", [(row["id"],) for row in rows])
        db.connection.commit()
    return len(rows)


def topic_plan(config: dict[str, Any], feed_path: Path, output_path: Path, limit: int) -> Path:
    data = load_json(feed_path)
    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("选题文件必须包含 items 数组")
    ranked: list[tuple[float, dict[str, Any]]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        scores = item.get("scores") or {}
        if all(key in scores for key in ("hook", "anxiety", "relevance")):
            overall = float(scores["hook"]) * 0.4 + float(scores["anxiety"]) * 0.3 + float(scores["relevance"]) * 0.3
        else:
            overall = 0.0
        ranked.append((overall, item))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    public_base = config["campaign"]["public_base_url"].rstrip("/")
    lines = [
        "# 内容选题执行单",
        "",
        "> 所有事实与链接必须发布前人工核对；分数只用于排序，不代表真实转化。",
        "",
        "| 排名 | 综合分 | 选题 | 来源 | 建议来源码 | 落地页链接 |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for index, (score, item) in enumerate(ranked[:limit], start=1):
        source_code = f"{config['campaign']['id']}-content-{index:03d}"
        link = item.get("link", "")
        platform = str(item.get("platform", "owned"))
        tracking = (
            f"{public_base}/?utm_source={urllib.parse.quote(platform)}"
            f"&src={urllib.parse.quote(source_code)}"
        )
        title = str(item.get("title", "未命名选题")).replace("|", "\\|")
        source = str(item.get("source", link)).replace("|", "\\|")
        lines.append(f"| {index} | {score:.1f} | {title} | {source} | `{source_code}` | {tracking} |")
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def command_init(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    db.close()
    print(f"数据库已初始化: {Path(args.data_dir).resolve() / 'creator-lead.sqlite3'}")
    site_path = Path(args.site) if args.site else Path(args.data_dir) / "landing.html"
    path = build_site(config, site_path, force=args.force)
    print(f"落地页已生成: {path}")
    print("下一步: 配置环境变量并运行 serve；worker 默认只预览，不会发送。")


def command_build_site(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    path = build_site(config, Path(args.output), force=args.force)
    print(f"落地页已生成: {path}")


def command_serve(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    server = CaptureServer((args.host, args.port), config, db)
    print(f"Listening on http://{args.host}:{args.port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        db.close()


def command_ingest(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    rows = import_rows(Path(args.file))
    created = 0
    duplicates = 0
    skipped = 0
    for row in rows:
        platform = clean_text(row.get("platform") or args.platform, 40)
        source_type = clean_text(row.get("source_type") or args.source_type, 40)
        raw_text = clean_text(row.get("raw_text") or row.get("intent_text") or row.get("message"), 1200)
        display_name = clean_text(row.get("display_name") or row.get("name"), 80)
        if not raw_text and not display_name:
            skipped += 1
            continue
        result = create_lead(
            db,
            config,
            source_channel=platform,
            source_type=source_type,
            source_code=clean_text(row.get("source_code"), 100),
            display_name=display_name,
            intent_text=raw_text,
            pain_point=clean_text(row.get("pain_point"), 1200),
            primary_goal=clean_text(row.get("primary_goal"), 120),
            allow_automation=False,
        )
        if result.duplicate:
            duplicates += 1
        else:
            created += 1
    db.close()
    print(f"导入完成: 新增 {created}，合并重复 {duplicates}，跳过 {skipped}")


def command_list(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    clauses = ["campaign_id = ?"]
    values: list[Any] = [config["campaign"]["id"]]
    if args.priority != "all":
        clauses.append("priority = ?")
        values.append(args.priority)
    if args.status != "all":
        clauses.append("status = ?")
        values.append(args.status)
    values.append(args.limit)
    rows = db.connection.execute(
        f"SELECT * FROM leads WHERE {' AND '.join(clauses)} ORDER BY "
        "CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at DESC LIMIT ?",
        values,
    ).fetchall()
    if args.format == "json":
        write_json(sys.stdout, [lead_to_dict(row, show_contact=args.show_contact) for row in rows])
    else:
        print_table(rows, show_contact=args.show_contact)
    db.close()


def command_update(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    update_lead_status(db, args.lead_id, args.status, owner=args.owner, note=args.note)
    db.close()
    print(f"线索 {args.lead_id} 已更新为 {args.status}")


def command_worker(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    count = run_worker(config, db, send=args.send, limit=args.limit)
    db.close()
    if not args.send and count:
        print("当前为 dry-run。确认邮件与 webhook 配置后加 --send 才会真正外发。")


def command_report(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    report = report_data(config, db)
    if args.format == "json":
        write_json(sys.stdout, report)
    else:
        print_report(report)
    db.close()


def command_export(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    count = export_leads(
        config,
        db,
        Path(args.output),
        anonymize=args.anonymize,
        include_pii=args.include_pii,
    )
    db.close()
    print(f"已导出 {count} 条线索到 {Path(args.output).resolve()}")
    if args.include_pii:
        print("注意：该文件含完整个人信息，只应存放在受保护目录，不得提交到公开仓库。")
    elif not args.anonymize:
        print("默认已脱敏联系方式和姓名；如需完整字段请加 --include-pii。")


def command_purge(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    db = Database(Path(args.data_dir))
    count = purge_leads(db, config, apply=args.apply)
    db.close()
    action = "已删除" if args.apply else "可删除"
    print(f"{action} {count} 条超过保留期限的线索。")
    if not args.apply and count:
        print("当前为 dry-run；确认后加 --apply。")


def command_topics(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config))
    path = topic_plan(config, Path(args.feed), Path(args.output), args.limit)
    print(f"选题执行单已生成: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Creator lead acquisition engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="initialize database and landing page")
    init.add_argument("--config", required=True)
    init.add_argument("--data-dir", required=True)
    init.add_argument("--site")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    site = subparsers.add_parser("build-site", help="export standalone landing page")
    site.add_argument("--config", required=True)
    site.add_argument("--output", required=True)
    site.add_argument("--force", action="store_true")
    site.set_defaults(func=command_build_site)

    serve = subparsers.add_parser("serve", help="serve landing page and capture endpoint")
    serve.add_argument("--config", required=True)
    serve.add_argument("--data-dir", required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.set_defaults(func=command_serve)

    ingest = subparsers.add_parser("ingest", help="import user-provided comments or leads")
    ingest.add_argument("--config", required=True)
    ingest.add_argument("--data-dir", required=True)
    ingest.add_argument("--file", required=True)
    ingest.add_argument("--platform", default="manual")
    ingest.add_argument("--source-type", default="comment")
    ingest.set_defaults(func=command_ingest)

    list_cmd = subparsers.add_parser("list", help="list leads")
    list_cmd.add_argument("--config", required=True)
    list_cmd.add_argument("--data-dir", required=True)
    list_cmd.add_argument("--priority", choices=["high", "medium", "low", "all"], default="all")
    list_cmd.add_argument("--status", choices=sorted(ALLOWED_STATUSES | {"all"}), default="all")
    list_cmd.add_argument("--limit", type=int, default=50)
    list_cmd.add_argument("--format", choices=["table", "json"], default="table")
    list_cmd.add_argument("--show-contact", action="store_true")
    list_cmd.set_defaults(func=command_list)

    update = subparsers.add_parser("update", help="record a pipeline status change")
    update.add_argument("--config", required=True)
    update.add_argument("--data-dir", required=True)
    update.add_argument("--lead-id", required=True)
    update.add_argument("--status", required=True, choices=sorted(ALLOWED_STATUSES))
    update.add_argument("--owner", default="")
    update.add_argument("--note", default="")
    update.set_defaults(func=command_update)

    worker = subparsers.add_parser("worker", help="process due email and webhook actions")
    worker.add_argument("--config", required=True)
    worker.add_argument("--data-dir", required=True)
    worker.add_argument("--send", action="store_true")
    worker.add_argument("--limit", type=int, default=100)
    worker.set_defaults(func=command_worker)

    report = subparsers.add_parser("report", help="show funnel report")
    report.add_argument("--config", required=True)
    report.add_argument("--data-dir", required=True)
    report.add_argument("--format", choices=["text", "json"], default="text")
    report.set_defaults(func=command_report)

    export = subparsers.add_parser("export", help="export leads to CSV")
    export.add_argument("--config", required=True)
    export.add_argument("--data-dir", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--anonymize", action="store_true")
    export.add_argument("--include-pii", action="store_true")
    export.set_defaults(func=command_export)

    purge = subparsers.add_parser("purge", help="delete expired person-level records")
    purge.add_argument("--config", required=True)
    purge.add_argument("--data-dir", required=True)
    purge.add_argument("--apply", action="store_true")
    purge.add_argument("--dry-run", action="store_true", help="default behavior; inspect expired records without deleting")
    purge.set_defaults(func=command_purge)

    topics = subparsers.add_parser("content-plan", help="rank user-provided news and build source codes")
    topics.add_argument("--config", required=True)
    topics.add_argument("--feed", required=True)
    topics.add_argument("--output", required=True)
    topics.add_argument("--limit", type=int, default=5)
    topics.set_defaults(func=command_topics)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, OSError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
