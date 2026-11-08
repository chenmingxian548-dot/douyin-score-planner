from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_release

class PortablePackageTests(unittest.TestCase):
    def test_workbuddy_package_has_direct_skill_entry_and_scripts(self):
        files=build_release.portable_payload('workbuddy')
        self.assertIn('douyin-score-planner/SKILL.md',files)
        self.assertIn('douyin-score-planner/scripts/planner.py',files)
        self.assertIn('douyin-score-planner/requirements.lock',files)
        self.assertFalse(any('/skills/' in x or '/.venv/' in x for x in files))
        header=files['douyin-score-planner/SKILL.md'].decode().split('---',2)[1]
        for key in ('name','display_name','display_name_en','description','description_zh','description_en','version','author'):
            self.assertTrue(any(line.startswith(key+':') for line in header.splitlines()),key)

    def test_unsupported_host_is_not_advertised_as_supported(self):
        with self.assertRaises(ValueError): build_release.portable_payload('doubao-chat')

if __name__=='__main__': unittest.main()
