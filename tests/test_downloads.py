from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/douyin-score-planner/scripts'))
import collect

class DownloadTests(unittest.TestCase):
    def test_old_file_is_not_a_completed_new_download(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);downloads=root/'downloads';downloads.mkdir()
            (downloads/'old.xlsx').write_bytes(b'old file')
            baseline=collect.inventory(downloads)
            with self.assertRaisesRegex(ValueError,'未观察到'):
                collect.verify_download(baseline,'reviews','synthetic-shop',root/'private',timeout=0)

    def test_incomplete_xlsx_is_not_accepted_or_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);downloads=root/'downloads';downloads.mkdir()
            baseline=collect.inventory(downloads)
            (downloads/'incomplete.xlsx').write_bytes(b'not a zip yet')
            with self.assertRaisesRegex(ValueError,'未观察到'):
                collect.verify_download(baseline,'reviews','synthetic-shop',root/'private',timeout=2)

    def test_real_new_file_is_checked_and_original_preserved(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);downloads=root/'downloads';downloads.mkdir();baseline=collect.inventory(downloads)
            path=downloads/'new.xlsx';w=openpyxl.Workbook();s=w.active
            s.append(['订单ID','商品ID','商品评分','签收时间','评价时间'])
            s.append(['fictional-order','fictional-product',5,'2030-01-01','2030-01-02']);w.save(path);w.close()
            r=collect.verify_download(baseline,'reviews','synthetic-shop',root/'private',expected_rows=1,timeout=3)
            self.assertEqual(r['status'],'download_verified')
            self.assertEqual(path.read_bytes(),Path(r['archived_file']).read_bytes())

if __name__=='__main__': unittest.main()
