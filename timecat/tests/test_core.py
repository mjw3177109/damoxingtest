"""Run: python -m unittest discover -s timecat/tests -v"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from timecat import core

class TestTimeCat(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/"state.sqlite"
        self.db=core.connect(self.path)
    def tearDown(self):
        self.db.close();self.tmp.cleanup()
    def test_identity_persistence(self):
        core.record(self.db,"identity","TimeCat starts today","user-confirmed")
        self.db.close()
        self.db=core.connect(self.path)
        self.assertEqual(core.snapshot(self.db)["experiences"],1)
    def test_dedup(self):
        for _ in range(2):core.record(self.db,"event","CI passed","run-101")
        self.assertEqual(core.snapshot(self.db)["experiences"],1)
    def test_memories_need_approval(self):
        ident=core.propose(self.db,"fact","T4 GPU used","run-12")
        self.assertEqual(core.recall(self.db,"GPU"),[])
        core.review(self.db,ident,True)
        self.assertEqual(len(core.recall(self.db,"GPU")),1)
    def test_correction_supersedes(self):
        old=core.propose(self.db,"fact","Run failed","run-1")
        core.review(self.db,old,True)
        new=core.propose(self.db,"fact","Run succeeded","run-2",old)
        core.review(self.db,new,True)
        self.assertEqual(len(core.recall(self.db,"Run")),1)
        self.assertIn("succeeded",core.recall(self.db,"Run")[0]["content"])
    def test_pending_cannot_correct(self):
        old=core.propose(self.db,"fact","x","source")
        with self.assertRaises(ValueError):core.propose(self.db,"fact","y","source",old)
    def test_reflection_is_proposal(self):
        self.assertIsNone(core.propose_reflection(self.db,"2026-10-29","summary"))
        core.record(self.db,"event","New CI evidence","run-12")
        self.assertIsNotNone(core.propose_reflection(self.db,"2026-10-29","summary"))
        self.assertIsNone(core.propose_reflection(self.db,"2026-10-29","same period"))
        self.assertEqual(core.snapshot(self.db)["pending_reflections"],1)
    def test_no_empty_or_unproven(self):
        with self.assertRaises(ValueError):core.record(self.db,"fact"," ","run")
        with self.assertRaises(ValueError):core.record(self.db,"fact","info","")
    def test_review_twice_fails(self):
        mid=core.propose(self.db,"lesson","Do not retrain without changes","run-12")
        core.review(self.db,mid,False)
        with self.assertRaises(ValueError):core.review(self.db,mid,True)
if __name__=="__main__":unittest.main()
