# ==========================
# VDB Core Integrity Test (Architecture-aligned)
# ==========================

import unittest

from core.vdb.app.vdb import embed_and_upsert
from core.vdb.app.db import VDBIndex
from core.vdb.app.models import init_db


class TestVDBCore(unittest.TestCase):

    def setUp(self):
        """
        Initialize clean DB state
        """
        init_db()
        self.index = VDBIndex(dim=512)


    # --------------------------
    # INDEX BUILD / REBUILD TEST
    # --------------------------
    def test_index_rebuild_from_db(self):
        """
        Ensures FAISS index can be rebuilt from SQLite source of truth
        """

        # --------------------------
        # STEP 1: Insert test data
        # --------------------------
        inserted_ids = []

        for i in range(5):
            doc_id = embed_and_upsert(
                text=f"dummy {i}",
                metadata={"source": "test"}
            )
            inserted_ids.append(doc_id)


        # --------------------------
        # STEP 2: Rebuild index from DB
        # --------------------------
        self.index.build_from_db()


        # --------------------------
        # STEP 3: Validate index state
        # --------------------------
        self.assertEqual(
            self.index.index.ntotal,
            5,
            "FAISS index size mismatch after rebuild"
        )

        self.assertEqual(
            len(self.index.ids),
            5,
            "ID mapping mismatch after rebuild"
        )


    # --------------------------
    # CONSISTENCY TEST
    # --------------------------
    def test_index_db_consistency(self):
        """
        Ensures SQLite and FAISS remain aligned
        """

        doc_id = embed_and_upsert(
            text="consistency check",
            metadata={"source": "test"}
        )

        self.index.build_from_db()

        self.assertIn(doc_id, self.index.ids)


if __name__ == "__main__":
    unittest.main()
