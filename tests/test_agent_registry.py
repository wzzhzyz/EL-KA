import unittest

from entity_linker.pipeline import EntityLinkingPipeline
from entity_linker.registry import registry


class AgentRegistryTests(unittest.TestCase):
    def test_default_agent_registered(self) -> None:
        self.assertIn("default", registry.list())
        factory = registry.get("default")
        self.assertIsNotNone(factory)
        pipeline = factory()
        self.assertIsInstance(pipeline, EntityLinkingPipeline)

    def test_agent_list_endpoint(self) -> None:
        from fastapi.testclient import TestClient

        from entity_linker.service import create_app

        app = create_app()
        client = TestClient(app)
        response = client.get("/agents")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("agents", payload)
        self.assertIn("default", payload["agents"])


if __name__ == "__main__":
    unittest.main()
