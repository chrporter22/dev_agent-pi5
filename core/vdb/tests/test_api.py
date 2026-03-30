# vdb/tests/test_api.py
import unittest
import json
from vdb.vdb import VDB
from vdb.config import Config

class TestVDBAPI(unittest.TestCase):
    def setUp(self):
        self.vdb = VDB(Config())
        self.sample_text = "Test embedding text"

    def test_embed(self):
        embedding = self.vdb.embed_text(self.sample_text)
        self.assertIsInstance(embedding, list)
        self.assertGreater(len(embedding), 0)

    def test_upsert_and_search(self):
        record_id = "test-id-1"
        embedding = self.vdb.embed_text(self.sample_text)
        self.vdb.upsert(record_id, self.sample_text, embedding, {"source": "unittest"})
        results = self.vdb.search(self.sample_text, top_k=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], record_id)

if __name__ == "__main__":
    unittest.main()
