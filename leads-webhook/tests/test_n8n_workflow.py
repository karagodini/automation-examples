from __future__ import annotations

import json
from pathlib import Path


def test_n8n_workflow_json_forwards_form_to_webhook() -> None:
    path = Path(__file__).resolve().parents[2] / "n8n" / "leads-workflow.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in workflow["nodes"]}
    assert nodes["Webhook"]["parameters"]["path"] == "website-lead"
    assert nodes["Webhook"]["parameters"]["httpMethod"] == "POST"
    assert "8000/leads" in nodes["Leads webhook"]["parameters"]["url"]
    assert nodes["Telegram"]["disabled"] is True
    assert nodes["Google Sheets"]["disabled"] is True
    targets = [item["node"] for item in workflow["connections"]["Webhook"]["main"][0]]
    assert targets == ["Leads webhook", "Telegram"]
