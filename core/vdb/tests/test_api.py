# ==========================
# VDB Integration Tests (Architecture-aligned)
# ==========================

import unittest
import uuid
import time

from core.vdb.app.vdb import embed_and_upsert, search_similar
from core.vdb.app.models import init_db


class TestVDBPipeline(unittest.TestCase):

    def setUp(self):
        """
        Ensure DB is initialized before tests
        """
        init_db()

        self.sample_text = "Test embedding text for VDB pipeline"
        self.test_id = str(uuid.uuid4())


    # --------------------------
    # EMBEDDING + UPSERT TEST
    # --------------------------
    def test_embed_and_upsert(self):
        doc_id = embed_and_upsert(
            text=self.sample_text,
            metadata={"source": "unittest"}
        )

        self.assertIsNotNone(doc_id)
        self.assertIsInstance(doc_id, str)


    # --------------------------
    # SEARCH INTEGRATION TEST
    # --------------------------
    def test_search_similarity(self):
        """
        This is an integration-style test.
        We verify system returns results, not exact ranking.
        """

        doc_id = embed_and_upsert(
            text=self.sample_text,
            metadata={"source": "unittest"}
        )

        time.sleep(0.1)  # allow index consistency (important for FAISS sync edge cases)

        results = search_similar(
            text=self.sample_text,
            top_k=3
        )

        # basic structural validation
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 1)

        # ensure at least one result contains valid structure
        first = results[0]
        self.assertIn("id", first)
        self.assertIn("score", first)


    # --------------------------
    # STABILITY TEST (NON-DETERMINISTIC SAFE)
    # --------------------------
    def test_retrieval_stability(self):
        """
        Ensures system does not crash under repeated queries
        """

        for _ in range(5):
            embed_and_upsert(
                text=self.sample_text,
                metadata={"source": "stability-test"}
            )

        results = search_similar(self.sample_text, top_k=5)

        self.assertTrue(len(results) > 0)


if __name__ == "__main__":
    unittest.main()
