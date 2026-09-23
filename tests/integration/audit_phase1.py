"""Record actual integrated HTTP responses using a disposable runtime store.

Run with .venv/bin/python tests/integration/audit_phase1.py [output.json].
No source dataset file is modified, and OpenAI is explicitly given an empty
environment so this reproducible audit never makes an external model request.
Runtime UUIDs and completion timestamps are real and vary between audit runs.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.data.loader import load_dataset
from backend.data.repository import DatasetRepository
from backend.integrations.recommendation_provider import RecommendationProvider
from backend.main import create_app


DATA_DIRECTORY = ROOT / "data" / "career_quest_dataset"


def dataset_hashes():
    return {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(DATA_DIRECTORY.iterdir()) if path.is_file()}


def response_json(response):
    if response.status_code != 200:
        raise AssertionError("{} {}: {}".format(
            response.request.method, response.request.url.path, response.text))
    return response.json()


def recommendations(client, employee_id):
    return response_json(client.get("/employees/{}/recommendations".format(employee_id)))


def profile(client, employee_id):
    return response_json(client.get("/employees/{}".format(employee_id)))


def completion(client, employee_id, event_id, key):
    return response_json(client.post(
        "/activities/{}/complete".format(event_id),
        json={"employee_id": employee_id},
        headers={"Idempotency-Key": key},
    ))


def app(repository, settings):
    return create_app(settings=settings, repository=repository,
                      recommendation_provider=RecommendationProvider(environ={}))


def run_audit():
    hashes_before = dataset_hashes()
    dataset = load_dataset(DATA_DIRECTORY)
    with TemporaryDirectory(prefix="career-quest-phase1-") as directory:
        runtime_path = Path(directory) / "runtime-state.json"
        repository = DatasetRepository(dataset, state_path=runtime_path)
        settings = Settings(data_dir=Path(directory) / "no-source-files",
                            runtime_state_path=None, auth_disabled=True)
        with TestClient(app(repository, settings)) as client:
            e0001 = {
                "before_profile": profile(client, "E0001"),
                "before_recommendations": recommendations(client, "E0001"),
            }
            e0001["completion"] = completion(client, "E0001", "EV_005", "phase1-e0001")
            e0001["after_profile"] = profile(client, "E0001")
            e0001["after_recommendations"] = recommendations(client, "E0001")
            e0001["idempotent_retry"] = completion(client, "E0001", "EV_005", "phase1-e0001")
            before = e0001["before_recommendations"]["data"]
            after = e0001["after_recommendations"]["data"]
            assert before["recommendations"][0]["event_id"] == "EV_005"
            assert before["recommendations"][0]["explanation"]["language"] == "kk"
            assert [item["event_id"] for item in after["recommendations"]] == ["EV_036"]
            assert e0001["before_profile"]["data"]["employee"] == e0001["after_profile"]["data"]["employee"]
            assert e0001["idempotent_retry"]["data"] == {
                **e0001["completion"]["data"], "replayed": True,
            }
        restored = DatasetRepository(dataset, state_path=runtime_path)
        with TestClient(app(restored, settings)) as client:
            e0001["after_restart_recommendations"] = recommendations(client, "E0001")
            e0001["after_restart_retry"] = completion(client, "E0001", "EV_005", "phase1-e0001")
            assert e0001["after_restart_recommendations"] == e0001["after_recommendations"]
            assert e0001["after_restart_retry"] == e0001["idempotent_retry"]
            e0004 = {
                "before_profile": profile(client, "E0004"),
                "before_recommendations": recommendations(client, "E0004"),
            }
            first = e0004["before_recommendations"]["data"]["recommendations"][0]
            assert first["event_id"] == "EV_026"
            assert first["evidence"]["audience_match"] == "target_role"
            e0004["completion"] = completion(client, "E0004", "EV_026", "phase1-e0004")
            e0004["after_profile"] = profile(client, "E0004")
            e0004["after_recommendations"] = recommendations(client, "E0004")
            assert e0004["before_profile"]["data"]["employee"] == e0004["after_profile"]["data"]["employee"]
            assert e0004["after_recommendations"]["data"]["career_readiness"]["current"] == first["simulation"]["readiness_after"]
            empty_results = {employee_id: recommendations(client, employee_id)
                             for employee_id in ("E0006", "E0018")}
            assert empty_results["E0006"]["data"]["status"] == "no_next_grade"
            assert empty_results["E0018"]["data"]["status"] == "no_eligible_recommendations"
        assert hashes_before == dataset_hashes()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "as_of": dataset.meta.as_of_date.isoformat(),
            "scope": "Actual FastAPI TestClient responses; disposable persisted runtime state; no frontend.",
            "openai": "Real explanation layer with empty environment: deterministic missing-key fallback; no live API call.",
            "clock": "completed_at is the real UTC operation timestamp; completed_on is the explicitly separate dataset simulation day.",
            "dataset_sha256_before": hashes_before,
            "dataset_sha256_after": dataset_hashes(),
            "e0001": e0001,
            "e0004": e0004,
            "empty_results": empty_results,
        }


if __name__ == "__main__":
    result = run_audit()
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "integration-phase1-results.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    example_path = destination.with_name("e0001-recommendations.response.json")
    example_path.write_text(json.dumps(result["e0001"]["before_recommendations"],
                                      ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for employee_id in ("e0001", "e0004"):
        flow = result[employee_id]
        before = flow["before_recommendations"]["data"]
        after = flow["after_recommendations"]["data"]
        print(employee_id.upper(), "readiness", before["career_readiness"]["current"], "->", after["career_readiness"]["current"],
              "recommendations", [item["event_id"] for item in before["recommendations"]], "->",
              [item["event_id"] for item in after["recommendations"]])
    print("Dataset hashes unchanged:", result["dataset_sha256_before"] == result["dataset_sha256_after"])
    print("Serialized actual HTTP responses:", destination)
    print("Complete E0001 recommendation response:", example_path)
