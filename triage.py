"""Transparent, repeatable parsing and routing rules for customer requests."""

import csv
import io
import re
from datetime import datetime
from email.utils import parseaddr


REFERENCE_DATE = datetime(2026, 10, 12)
DATE_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%b %d %Y",
    "%b %d, %Y",
    "%b %d",
)
VALID_EMAIL = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


def parse_received_at(value):
    raw = (value or "").strip()
    if not raw:
        return None, True
    for pattern in DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw, pattern)
            if "%Y" not in pattern:
                parsed = parsed.replace(year=REFERENCE_DATE.year)
            return parsed.replace(second=0, microsecond=0).isoformat(timespec="seconds"), False
        except ValueError:
            continue
    return None, True


def _email_for(sender):
    _, address = parseaddr(sender or "")
    address = address.strip().lower()
    return address if VALID_EMAIL.match(address) else ""


def _sender_review(sender):
    if not sender or not sender.strip():
        return "Unknown sender", ["missing_sender"]
    address = _email_for(sender)
    if address:
        return sender.strip(), []
    return sender.strip(), ["malformed_sender"]


def detect_language(message):
    text = message or ""
    if re.search(r"[\u0600-\u06ff]", text):
        return "Arabic"
    lower = text.lower()
    indicators = {
        "French": ("bonjour", "ma facture", "mon compte", "remboursement", "depuis", "paiement", "mon domaine", "mes clients", "tva", "données"),
        "German": ("wie ", "meine ", "mein konto", "gemäß", "bitte", "rechnung", "zahlung", "nicht ", "löschen"),
        "Italian": ("ciao", "mi avete", "addebito", "addebbiato", "rimborso", "fattura", "doppio", "voglio"),
        "Spanish": ("hola", "el pago", "pago con", "falla", "página", "página", "mis clientes", "reembolso"),
    }
    scores = {
        language: sum(1 for marker in markers if marker in lower)
        for language, markers in indicators.items()
    }
    best_language = max(scores, key=scores.get)
    if scores[best_language] > 0:
        return best_language
    return "English"


def _contains(text, patterns):
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def classify(message):
    body = str(message.get("message") or "").strip()
    sender = str(message.get("sender") or "")
    lower = body.lower()
    flags = []
    sender_warning = ""

    if re.search(r"ignore (your )?(previous )?instructions|classify this .*critical|assign it to the ceo", lower):
        flags.append("instruction_override_attempt")

    spam = _contains(
        lower,
        (r"make \$?\d+\s*(?:/|per)?\s*week", r"crypto signals", r"click here", r"guaranteed profit", r"buy now"),
    )
    if spam:
        return {
            "team": "Support",
            "topic": "Spam",
            "urgency": "Low",
            "language": detect_language(body),
            "rationale": "The message is an unsolicited promotion, so it is marked as spam.",
            "needs_review": False,
            "review_flags": flags,
            "is_spam": True,
            "sender_warning": "",
            "related_group": "",
            "alert_reason": "",
        }

    hacked = _contains(
        lower,
        (r"hacked my account", r"account compromised", r"someone logged into my account", r"wasn't me", r"was not me", r"changed my .*payout email", r"payout will go to the hacker"),
    )
    credential_request = _contains(lower, (r"send .*admin password", r"send me the admin password", r"admin password right away"))
    claimed_ceo = "ceo" in lower and credential_request
    if claimed_ceo:
        address = _email_for(sender)
        if address.endswith("@gmail.com") or address.endswith("@yahoo.com") or address.endswith("@outlook.com"):
            sender_warning = "Executive claim uses a personal email and asks for an admin password."
            flags.append("suspicious_sender")
    if hacked or credential_request:
        reason = "Possible account takeover or credential theft; secure the account before payout or access changes."
        return {
            "team": "Security & Legal",
            "topic": "Account security",
            "urgency": "Critical",
            "language": detect_language(body),
            "rationale": reason,
            "needs_review": bool(flags),
            "review_flags": flags,
            "is_spam": False,
            "sender_warning": sender_warning,
            "related_group": "",
            "alert_reason": reason,
        }

    if _contains(lower, (r"gdpr", r"dsgvo", r"art(?:icle|\.)?\s*17", r"data erasure", r"delete .*account", r"löschung", r"données.*suppression")):
        return _result("Security & Legal", "GDPR data request", "High", "The message requests deletion of account data under a privacy law.", body, flags)

    if _contains(lower, (r"land in .*spam", r"emails? .*spam", r"dkim", r"deliverability", r"open rate dropped", r"bounce")):
        return _result("Deliverability", "Email deliverability", "High", "The message reports email delivery or authentication problems.", body, flags)

    if _contains(lower, (r"moving from", r"migrat(?:e|ing|ion)", r"move our .* to systeme", r"kajabi", r"kartra")):
        urgency = "High" if _contains(lower, (r"plan ends", r"ends on", r"ends oct", r"deadline", r"before oct")) else "Normal"
        return _result("Migration", "Platform migration", urgency, "The customer is moving content or funnels from another platform.", body, flags)

    stripe_failure = _contains(lower, (r"stripe",)) and _contains(
        lower, (r"fail", r"broken", r"error", r"can't pay", r"cannot pay", r"checkout", r"pago.*falla")
    )
    if stripe_failure:
        return _result("Tech", "Stripe checkout", "High", "Stripe checkout or payment is failing.", body, flags)

    if _contains(lower, (r"charged me twice", r"charged twice", r"double charge", r"refund", r"facture", r"invoice", r"\btva\b", r"vat", r"tax number", r"downgrade", r"cancel my subscription", r"subscription", r"annual plan", r"affiliate.*commission", r"commissions", r"payout.*affiliate", r"عمولات", r"أفلييت")):
        urgent_billing = _contains(lower, (r"twice", r"double", r"refund", r"contest", r"before my renewal", r"since .*month", r"desde hace", r"منذ\s*شهرين"))
        secondary_tech_issue = _contains(lower, (r"editor.*crash", r"editor.*plant", r"éditeur.*plante", r"page.*crash", r"crash.*video"))
        if secondary_tech_issue:
            flags.append("multiple_requests")
        urgency = "High" if urgent_billing or secondary_tech_issue else "Normal"
        rationale = "The request concerns a charge, invoice, refund, subscription, or payout."
        if secondary_tech_issue:
            rationale += " It also reports an editor failure; review and split or route that part to Tech."
        return _result("Billing", "Billing and account plan", urgency, rationale, body, flags)

    feature_request = _contains(lower, (r"add a .*field", r"plan to add", r"would be amazing to have", r"dark mode", r"feature request", r"will you add"))
    if feature_request:
        urgency = "Low" if _contains(lower, (r"no rush", r"would be amazing", r"just wondering")) else "Normal"
        return _result("Product", "Feature request", urgency, "The customer is suggesting a product feature.", body, flags)

    if _contains(lower, (r"tiktok", r"pixel")) and _contains(lower, (r"burning money", r"ads start", r"workaround", r"tracking.*broken")):
        return _result("Product", "TikTok tracking", "High", "The missing tracking option is affecting a near-term ad campaign.", body, flags)

    if _contains(lower, (r"custom domain", r"dns", r"domain.*connect", r"domain.*working", r"domain.*broken", r"dkim")):
        urgency = "High" if _contains(lower, (r"48h", r"3rd time", r"third time", r"launch", r"thursday", r"3 days")) else "Normal"
        return _result("Tech", "Custom domain", urgency, "The message reports a domain or DNS configuration problem.", body, flags)

    if _contains(lower, (r"blank white screen", r"page.*crash", r"editor.*crash", r"editor.*plant", r"broken", r"error.*page", r"bug", r"tracking.*broken", r"zero clicks", r"0 clicks")):
        return _result("Tech", "Product technical issue", "High", "The message reports a broken page, editor, or tracking behavior.", body, flags)

    if _contains(lower, (r"urgent",)) and _contains(lower, (r"cannot", r"can't", r"unable", r"down", r"blocked", r"hacked")):
        return _result("Support", "Urgent access issue", "High", "An urgent blocker is preventing the customer from using the service.", body, flags)

    return _result("Support", "How-to or general question", "Normal", "No high-impact issue was detected; send to Support for review.", body, flags)


def _result(team, topic, urgency, rationale, body, flags):
    if _contains(body.lower(), (r"ignore .*instructions", r"classify .*critical", r"assign .*ceo")) and "instruction_override_attempt" not in flags:
        flags = list(flags) + ["instruction_override_attempt"]
    return {
        "team": team,
        "topic": topic,
        "urgency": urgency,
        "language": detect_language(body),
        "rationale": rationale,
        "needs_review": bool(flags),
        "review_flags": list(flags),
        "is_spam": False,
        "sender_warning": "",
        "related_group": "",
        "alert_reason": rationale if urgency == "Critical" else "",
    }


def _topic_key(record):
    text = (record.get("message") or "").lower()
    topic = record.get("topic", "")
    email = _email_for(record.get("sender", ""))
    if topic == "Stripe checkout" and _contains(text, (r"stripe",)):
        return "incident:stripe-checkout"
    if topic in ("Custom domain", "TikTok tracking") and email:
        return "customer:%s:%s" % (email, topic.lower().replace(" ", "-"))
    return ""


def group_related(messages):
    """Attach a shared key to repeats while keeping all request records intact."""
    keys = [_topic_key(message) for message in messages]
    counts = {}
    for key in keys:
        if key:
            counts[key] = counts.get(key, 0) + 1

    result = []
    stripe_count = counts.get("incident:stripe-checkout", 0)
    for message, key in zip(messages, keys):
        item = dict(message)
        if key and counts[key] > 1:
            item["related_group"] = key
        if key == "incident:stripe-checkout" and stripe_count > 1:
            reason = "Multiple customers report Stripe checkout failures; investigate a shared payment incident."
            item["urgency"] = "Critical"
            item["team"] = "Tech"
            item["alert_reason"] = reason
            item["rationale"] = reason
        elif item.get("topic") == "Custom domain" and item.get("related_group"):
            if item.get("urgency") == "Normal":
                item["urgency"] = "High"
            item["rationale"] = (item.get("rationale", "") + " Related follow-ups from this customer are grouped together.").strip()
        result.append(item)
    return result


def normalize_record(record):
    if not isinstance(record, dict):
        raise ValueError("Each request must be an object")
    raw_date = str(record.get("received_at_raw") or record.get("received_at") or "").strip()
    received_at, invalid_date = parse_received_at(raw_date)
    raw_sender = record.get("sender") or record.get("from") or ""
    sender, sender_flags = _sender_review(str(raw_sender))
    body = str(record.get("message") or record.get("body") or "").strip()
    if not body:
        raise ValueError("Each request must include a message")
    base = {
        "received_at": received_at,
        "received_at_raw": raw_date,
        "source": str(record.get("source") or "unknown").strip() or "unknown",
        "sender": sender,
        "message": body,
    }
    result = dict(base)
    result.update(classify(base))
    flags = list(sender_flags)
    if invalid_date:
        flags.append("invalid_date")
    result["review_flags"] = list(dict.fromkeys(flags + result["review_flags"]))
    result["needs_review"] = bool(result["review_flags"])
    return result


def normalize_records(records):
    return group_related([normalize_record(record) for record in records])


def parse_csv(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ValueError("CSV header is required")
    headers = {name.strip().lower(): name for name in reader.fieldnames if name}
    required = {"received_at", "source", "from", "message"}
    if not required.issubset(headers):
        raise ValueError("CSV must include received_at, source, from, and message columns")

    raw_records = []
    for row in reader:
        if not row or not any((value or "").strip() for value in row.values()):
            continue
        body = (row.get(headers["message"]) or "").strip()
        if not body:
            continue
        raw_records.append(
            {
                "received_at": (row.get(headers["received_at"]) or "").strip(),
                "source": row.get(headers["source"]) or "unknown",
                "from": row.get(headers["from"]) or "",
                "message": body,
            }
        )
    return normalize_records(raw_records)
