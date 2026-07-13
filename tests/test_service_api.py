import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from entity_linker.pipeline import EntityLinkingPipeline
from entity_linker.service import create_app


class ServiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")

    def test_link_endpoint_accepts_mentions(self) -> None:
        response = self.client.post(
            "/v1/link",
            json={
                "text": "国家电网发布了公告。",
                "mentions": [
                    {
                        "mention": "国家电网",
                        "type": "ORG",
                        "char_start": 0,
                        "char_end": 4,
                        "confidence": 1.0,
                    }
                ],
                "options": {"enable_coreference": False},
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["input_mode"], "provided_mentions")
        self.assertTrue(payload["results"])
        self.assertIn("link_basis", payload["results"][0])

    def test_service_writes_trace_record_for_mentions_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "trace.db"
            pipeline = EntityLinkingPipeline(
                {
                    "entity_alignment": {"enabled": False},
                    "prefer_bge": False,
                    "db_path": str(db_path),
                }
            )
            client = TestClient(create_app(pipeline))
            response = client.post(
                "/v1/link",
                json={
                    "text": "国家电网发布了公告。",
                    "mentions": [
                        {
                            "mention": "国家电网",
                            "type": "ORG",
                            "char_start": 0,
                            "char_end": 4,
                            "confidence": 1.0,
                        }
                    ],
                    "options": {"enable_coreference": False},
                },
            )
            self.assertEqual(response.status_code, 200)
            trace_id = response.json()["trace_id"]
            self.assertTrue(db_path.exists())

            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute(
                    "SELECT run_id, status FROM pipeline_run WHERE run_id = ?",
                    (trace_id,),
                ).fetchone()
            finally:
                conn.close()

            self.assertIsNotNone(row)
            self.assertEqual(row[1], "success")


if __name__ == "__main__":
    unittest.main()
