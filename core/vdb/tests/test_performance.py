# vdb/tests/test_performance.py
import unittest
import time
from vdb.vdb import VDB
from vdb.config import Config

class TestVDBPerformance(unittest.TestCase):
    def setUp(self):
        self.vdb = VDB(Config())
        # Insert 10k dummy records for performance test
        for i in range(10000):
            text = f"perf record {i}"
            emb = self.vdb.embed_text(text)
            self.vdb.upsert(f"id_{i}", text, emb, {"source": "perf"})

    def test_search_latency(self):
        start = time.time()
        results = self.vdb.search("perf record 9999", top_k=5)
        duration = time.time() - start
        self.assertLess(duration, 0.05, "Search latency exceeded 50ms")
        self.assertEqual(len(results), 5)

if __name__ == "__main__":
    unittest.main()
