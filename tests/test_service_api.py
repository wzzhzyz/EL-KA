import unittest

from fastapi.testclient import TestClient

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


if __name__ == "__main__":
    unittest.main()
