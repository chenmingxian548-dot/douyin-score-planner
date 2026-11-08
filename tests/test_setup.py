import importlib.util
from pathlib import Path
import tempfile
import unittest
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/douyin-score-planner/scripts'
spec=importlib.util.spec_from_file_location('skill_setup',SCRIPTS/'setup.py')
setup=importlib.util.module_from_spec(spec);spec.loader.exec_module(setup)

class SetupTests(unittest.TestCase):
    def test_shell_cannot_claim_host_computer_use(self):
        r=setup.doctor()
        self.assertEqual(r['automatic_collection']['status'],'requires_host_probe')
        self.assertFalse(r['automatic_collection']['ready'])

    def test_install_is_idempotent_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'source';src.mkdir();(src/'SKILL.md').write_text('synthetic skill')
            dest=root/'installed'
            self.assertEqual(setup.install_skill(src,dest)['status'],'installed')
            self.assertEqual(setup.install_skill(src,dest)['status'],'already_installed')
            (dest/'SKILL.md').write_text('user changes')
            with self.assertRaises(ValueError): setup.install_skill(src,dest)

if __name__=='__main__': unittest.main()
