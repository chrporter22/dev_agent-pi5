# vdb/tests/test_vdb.py
import unittest
from vdb.vdb import VDB
from vdb.config import Config

class TestVDBCore(unittest.TestCase):
    def setUp(self):
        self.vdb = VDB(Config())
    
    def test_index_rebuild(self):
        # Upsert dummy data
        for i in range(5):
            text = f"dummy {i}"
            emb = self.vdb.embed_text(text)
            self.vdb.upsert(f"id_{i}", text, emb, {"source": "test"})
        # Rebuild index
        self.vdb.rebuild_index()
        self.assertEqual(self.vdb.index.ntotal, 5)

if __name__ == "__main__":
    unittest.main()
