# Request Triage

A small internal demo for sorting incoming Systeme.io customer messages by team, urgency, topic, and language.

## Start the app

This demo needs Python 3.9 or newer and has no third-party dependencies.

```bash
python3 app.py
```

Open <http://127.0.0.1:8000>. The app stores its data in `data/requests.sqlite3`.

## How it works

The dashboard and SQLite database are the working tool. Import `data/requests-backlog.csv` from the **Import CSV** button to load the sample inbox. The n8n workflow receives a CSV or request payload and forwards it to the app. The app applies visible rules, stores each original message, and creates an alert for critical requests. Similar Stripe failures are grouped as one incident without deleting individual messages.

Classification is rule-based so the reasons are visible and repeatable. Customer text is treated as data; it cannot change its own team or urgency. Unclear senders, dates, or messages are flagged for review.

## Connect n8n

1. Import `n8n/request-intake.json` into your n8n instance.
2. In the HTTP Request node, change the URL to the address where this app can be reached, ending in `/api/intake`.
3. Create a **Header Auth** credential named `Request Triage API Bearer`. Set the header name to `Authorization` and the value to `Bearer <your-token>`, then select it in the node.
4. Start the app with the same token: `INTAKE_TOKEN=<your-token> python3 app.py`.
5. Save and activate the workflow. Send a CSV body or JSON body such as `{ "messages": [{ "received_at": "2026-10-12 08:30", "source": "form", "from": "person@example.com", "message": "My checkout is broken" }] }` to the n8n webhook URL.

The workflow is inactive until you configure its URL and credential. Keep its webhook private or add webhook authentication before connecting real customer sources.

## Tests

```bash
python3 -m unittest discover -v
```

The tests cover CSV parsing, the 30-message backlog, classification rules, API updates, and the exported workflow structure. This environment does not have n8n installed, so the workflow has not been run inside an n8n instance.

## Demo limits

- External email or chat notifications are not connected. Critical items appear in the app's alert panel.
- There is no user login or secure separation between teams. Use only the supplied test data, not real customer messages.
- The inbox uses the fixed test reference date of Monday, October 12, 2026.
