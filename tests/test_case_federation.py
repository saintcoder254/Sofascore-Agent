import os, tempfile, unittest
from store import Store
from case_database import CaseDatabase

class TestCaseFederation(unittest.TestCase):
    def test_case_events_federate_once(self):
        fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        cfd,cpath=tempfile.mkstemp(suffix='.db'); os.close(cfd)
        try:
            store=Store(path); case=CaseDatabase(cpath,'fixture-1')
            case.record_observation('TEST','agent','source',{'x':1})
            events=case.export_audit_events()
            self.assertEqual(store.federate_case_events('fixture-1',events),1)
            self.assertEqual(store.federate_case_events('fixture-1',events),0)
            self.assertTrue(store.verify_global_audit()['valid'])
        finally:
            try: os.remove(path)
            except OSError: pass
            try: os.remove(cpath)
            except OSError: pass

if __name__=='__main__': unittest.main()
