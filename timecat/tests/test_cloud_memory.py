"""V2 cloud memory tests; fake remote is isolated and contains no user data."""
import json
import tempfile
import unittest
from pathlib import Path
from timecat.cloud_memory import MemoryStore, SupabaseMemoryClient, synchronize, SyncConflict

class FakeCloud:
    def __init__(self):self.rows={}
    def get(self,uid):return self.rows.get(uid)
    def list_all(self):return list(self.rows.values())
    def create(self,entry):
        r={k:entry[k] for k in ("id","kind","content","source","status","created_at","updated_at")}
        r["revision"]=1
        if r["id"] in self.rows:raise SyncConflict("duplicate")
        self.rows[r["id"]]=r.copy()
        return r.copy()
    def update(self,entry):
        r=self.rows.get(entry["id"])
        if r is None or r["revision"]!=entry["remote_revision"]:raise SyncConflict("stale")
        r.update(status=entry["status"],updated_at=entry["updated_at"],revision=r["revision"]+1)
        return r.copy()

class CloudMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.cloud=FakeCloud()
        self.one=MemoryStore(self.path/"one.sqlite")
    def tearDown(self):
        self.one.close();self.tmp.cleanup()
    def test_restart_and_private_approval(self):
        mid=self.one.propose("lesson","repair, verify, train","manual-confirmed")
        self.assertEqual(self.one.recall("repair"),[])
        self.one.review(mid,True)
        self.one.close();self.one=MemoryStore(self.path/"one.sqlite")
        self.assertEqual(len(self.one.recall("repair")),1)
    def test_cross_session_cloud_recovery(self):
        mid=self.one.propose("preference","bobo is TimeCat's mentor","user-explicit")
        self.one.review(mid,True)
        a=synchronize(self.one,self.cloud)
        self.assertTrue(a["cloud_confirmed"])
        other=MemoryStore(self.path/"other.sqlite")
        try:
            synchronize(other,self.cloud)
            self.assertEqual(other.recall("bobo")[0]["id"],mid)
        finally:other.close()
    def test_unapproved_not_recalled_other_client(self):
        self.one.propose("fact","unverified guess","test")
        synchronize(self.one,self.cloud)
        second=MemoryStore(self.path/"second.sqlite")
        try:
            synchronize(second,self.cloud)
            self.assertEqual(second.recall("unverified"),[])
        finally:second.close()
    def test_conflict_preserves_local(self):
        mid=self.one.propose("lesson","original","source")
        synchronize(self.one,self.cloud)
        self.one.review(mid,True)
        self.cloud.rows[mid]["revision"]+=1
        with self.assertRaises(SyncConflict):synchronize(self.one,self.cloud)
        self.assertEqual(self.one.counts()["unsynced"],1)
    def test_sync_repeated_no_duplicate(self):
        self.one.propose("fact","original","source")
        synchronize(self.one,self.cloud)
        summary=synchronize(self.one,self.cloud)
        self.assertEqual(summary["uploaded"],0)
        self.assertEqual(len(self.cloud.rows),1)
    def test_approved_on_other_client_after_sync(self):
        mid=self.one.propose("goal","achieve reliable memory","source")
        synchronize(self.one,self.cloud)
        other=MemoryStore(self.path/"other.sqlite")
        try:
            synchronize(other,self.cloud)
            other.review(mid,True)
            synchronize(other,self.cloud)
            synchronize(self.one,self.cloud)
            self.assertEqual(len(self.one.recall("reliable")),1)
        finally:other.close()
    def test_wrong_url_fails_closed(self):
        with self.assertRaises(ValueError):
            SupabaseMemoryClient("http://127.0.0.1:8000","public","private")
    def test_missing_jwt_fails_closed(self):
        with self.assertRaises(ValueError):
            SupabaseMemoryClient("https://example.supabase.co","public","")
    def test_approval_after_local_unsynced(self):
        mid=self.one.propose("lesson","tested rule","test")
        self.one.review(mid,True)
        synchronize(self.one,self.cloud)
        self.assertEqual(self.cloud.rows[mid]["status"],"approved")
        self.assertEqual(self.cloud.rows[mid]["revision"],1)
if __name__=="__main__":unittest.main()
