# ==========================
# VDB Performance Benchmark (Safe + CI-friendly)
# ==========================

import unittest
import time
import uuid

from core.vdb.app.vdb import embed_and_upsert, search_similar


class TestVDBPerformance(unittest.TestCase):

    def setUp(self):
        """
        DO NOT preload 10k records here.
        That breaks test isolation and persistence.
        """
        self.test_docs = []

        # lightweight warmup dataset (safe for CI)
        for i in range(200):
            doc_id = embed_and_upsert(
                text=f"performance test record {i}",
                metadata={"source": "perf-test"}
            )
            self.test_docs.append(doc_id)


    # --------------------------
    # SEARCH LATENCY TEST
    # --------------------------
    def test_search_latency(self):
        query = "performance test record 199"

        start = time.perf_counter()
        results = search_similar(query, top_k=5)
        duration = time.perf_counter() - start

        # realistic threshold for containerized FAISS + Python
        self.assertLess(
            duration,
            0.2,
            f"Search latency too high: {duration:.4f}s"
        )

        self.assertGreater(len(results), 0)


    # --------------------------
    # INGESTION PERFORMANCE TEST
    # --------------------------
    def test_ingestion_throughput(self):
        start = time.perf_counter()

        for i in range(100):
            embed_and_upsert(
                text=f"throughput test {i}",
                metadata={"source": "perf"}
            )

        duration = time.perf_counter() - start
        throughput = 100 / duration

        # sanity threshold (not strict CI break)
        self.assertGreater(
            throughput,
            10,
            f"Throughput too low: {throughput:.2f} ops/sec"
        )


    # --------------------------
    # STABILITY UNDER REPEATED QUERIES
    # --------------------------
    def test_repeated_search_stability(self):
        for _ in range(20):
            results = search_similar(
                "performance test record 10",
                top_k=3
            )
            self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
