from pathlib import Path
import unittest

class PortalTests(unittest.TestCase):
    def test_portal_uses_right_project(self):
        page = (Path(__file__).resolve().parents[1] / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('svlxyknltmeninipjrxo.supabase.co', page)
        self.assertIn('timecat_memory_v2', page)
        self.assertIn('status=eq.proposed', page)
        self.assertIn('revision=eq.', page)
        self.assertIn('grant_type=password', page)

if __name__ == '__main__': unittest.main()
