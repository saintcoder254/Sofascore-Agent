import os
import tempfile
import unittest
from store import Store

class TestGlobalAuditLedger(unittest.TestCase):
    def test_prediction_and_outcome_are_audited(self):
        fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        try:
            s=Store(path)
            s.add_prediction('p1','f1','DOUBLE_CHANCE',0.68,'X2',1.70,model_version='test',features={'competition':'test'})
            s.record_outcome('p1',0.0)
            report=s.global_audit_summary()
            self.assertEqual(report['events'],2)
            self.assertTrue(report['chain']['valid'])
        finally:
            try: os.remove(path)
            except OSError: pass

    def test_prediction_id_conflict_is_rejected(self):
        fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        try:
            s=Store(path)
            s.add_prediction('p1','f1','1X2',0.60,'HOME',2.00,model_version='a')
            with self.assertRaises(ValueError):
                s.add_prediction('p1','f2','1X2',0.70,'AWAY',2.00,model_version='b')
        finally:
            try: os.remove(path)
            except OSError: pass

    def test_global_audit_tamper_is_detected(self):
        fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        try:
            s=Store(path)
            s.add_prediction('p1','f1','1X2',0.60,'HOME',2.00)
            s.db.execute("UPDATE omega_global_audit SET payload_json=? WHERE sequence=1", ('{"tampered":true}',))
            s.db.commit()
            self.assertFalse(s.verify_global_audit()['valid'])
        finally:
            try: os.remove(path)
            except OSError: pass

if __name__=='__main__': unittest.main()
