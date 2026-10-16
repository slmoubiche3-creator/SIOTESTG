import json
import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "n8n" / "request-intake.json"


class N8nWorkflowTests(unittest.TestCase):
    def test_workflow_has_intake_webhook_and_app_api_request(self):
        workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
        nodes = {node["name"]: node for node in workflow["nodes"]}
        self.assertIn("Receive customer requests", nodes)
        self.assertIn("Classify and store requests", nodes)

        webhook = nodes["Receive customer requests"]
        self.assertEqual(webhook["type"], "n8n-nodes-base.webhook")
        self.assertEqual(webhook["parameters"]["httpMethod"], "POST")
        self.assertEqual(webhook["parameters"]["path"], "request-intake")
        self.assertEqual(webhook["parameters"]["responseMode"], "lastNode")

        request = nodes["Classify and store requests"]
        self.assertEqual(request["type"], "n8n-nodes-base.httpRequest")
        self.assertEqual(request["parameters"]["method"], "POST")
        self.assertIn("/api/intake", request["parameters"]["url"])
        self.assertEqual(request["parameters"]["authentication"], "genericCredentialType")
        self.assertIn("httpHeaderAuth", request["credentials"])
        self.assertIn("REPLACE", request["credentials"]["httpHeaderAuth"]["id"])

        connection = workflow["connections"]["Receive customer requests"]["main"][0][0]
        self.assertEqual(connection["node"], "Classify and store requests")
        self.assertFalse(workflow["active"])


if __name__ == "__main__":
    unittest.main()
