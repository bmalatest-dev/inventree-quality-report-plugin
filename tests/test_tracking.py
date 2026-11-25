import unittest
from inventree_quality_report.tracking import merge_audit_deltas, load_tracking


class TrackingTests(unittest.TestCase):
    def test_migrated_status(self):
        self.assertEqual(merge_audit_deltas({'status': [75, 10], 'status_custom_key': [20, 8]}, {'tracking_id': 43110}), {'status': [75, 10], 'status_custom_key': [20, 8]})

    def test_event_deltas(self):
        self.assertEqual(merge_audit_deltas({'status': [10, 75]}, {'deltas': {'quantity': 2, 'status': 75}}), {'status': [10, 75], 'quantity': 2})

    def test_missing_data(self):
        self.assertEqual(merge_audit_deltas(None, None), {})
        self.assertEqual(merge_audit_deltas(None, {'deltas': {'status': 20}}), {'status': 20})

    def test_empty_stock(self):
        self.assertEqual(load_tracking(None, []), [])
