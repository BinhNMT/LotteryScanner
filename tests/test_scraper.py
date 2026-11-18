"""Unit tests for the xsmn.mobi HTML parser and sync pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lotto_store import (
    LotterySyncInput,
    XsmnPrizes,
    get_all_results,
    get_result_by_province,
    parse_xsmn_mobi_html,
    sync_from_xsmn_mobi,
    upsert_result,
)

SAMPLE_HTML = """
<div>
  <a class="vietlott-link" href="/xsmn-16-11-2026.html">XSMN ngày 16-11-2026</a>
</div>
<div id="load_kq_mn_1">
  <table class="extendable read-result badai colgiai">
    <thead>
      <tr>
        <th class="first"></th>
        <th data-pid="14" data-pcode="hcm"><a href="#">TP HCM</a></th>
        <th data-pid="12" data-pcode="dt"><a href="#">Đồng Tháp</a></th>
      </tr>
    </thead>
    <tbody>
      <tr class="g8"><td>G8</td><td><div class="v-g8">05</div></td><td><div class="v-g8">19</div></td></tr>
      <tr><td>G7</td><td><div class="v-g7">012</div></td><td><div class="v-g7">345</div></td></tr>
      <tr><td>G6</td><td><div>0011</div><div>2233</div><div>4455</div></td><td><div>1111</div><div>2222</div><div>3333</div></td></tr>
      <tr><td>G5</td><td><div>0987</div></td><td><div>6543</div></td></tr>
      <tr><td>G4</td><td><div>00001</div><div>00002</div><div>00003</div><div>00004</div><div>00005</div><div>00006</div><div>00007</div></td><td><div>10001</div><div>10002</div><div>10003</div><div>10004</div><div>10005</div><div>10006</div><div>10007</div></td></tr>
      <tr><td>G3</td><td><div>12345</div><div>67890</div></td><td><div>23456</div><div>78901</div></td></tr>
      <tr><td>G2</td><td><div>04567</div></td><td><div>54321</div></td></tr>
      <tr><td>G1</td><td><div>08888</div></td><td><div>99999</div></td></tr>
      <tr class="gdb"><td>ĐB</td><td><div>012345</div></td><td><div>987654</div></td></tr>
    </tbody>
  </table>
</div>

<div>
  <a class="vietlott-link" href="/xsmn-14-11-2026.html">XSMN ngày 14-11-2026</a>
</div>
<div id="load_kq_mn_3">
  <table class="extendable read-result bondai colgiai">
    <thead>
      <tr>
        <th class="first"></th>
        <th data-pid="14" data-pcode="hcm"><a href="#">TP HCM</a></th>
        <th data-pid="16" data-pcode="la"><a href="#">Long An</a></th>
      </tr>
    </thead>
    <tbody>
      <tr class="g8"><td>G8</td><td><div>99</div></td><td><div>...</div></td></tr>
      <tr><td>G7</td><td><div>999</div></td><td><div>...</div></td></tr>
      <tr><td>G6</td><td><div>9991</div><div>9992</div><div>9993</div></td><td><div>...</div></td></tr>
      <tr><td>G5</td><td><div>9994</div></td><td><div>...</div></td></tr>
      <tr><td>G4</td><td><div>90001</div><div>90002</div><div>90003</div><div>90004</div><div>90005</div><div>90006</div><div>90007</div></td><td><div>...</div></td></tr>
      <tr><td>G3</td><td><div>91111</div><div>92222</div></td><td><div>...</div></td></tr>
      <tr><td>G2</td><td><div>93333</div></td><td><div>...</div></td></tr>
      <tr><td>G1</td><td><div>94444</div></td><td><div>...</div></td></tr>
      <tr class="gdb"><td>ĐB</td><td><div>955555</div></td><td><div>...</div></td></tr>
    </tbody>
  </table>
</div>
"""


class ScraperTests(unittest.TestCase):
    def test_parse_deduplicates_latest_and_skips_incomplete(self) -> None:
        records, skipped = parse_xsmn_mobi_html(SAMPLE_HTML)

        self.assertEqual(len(skipped), 1)
        self.assertIn("LA (2026-11-14)", skipped[0])

        by_code = {item.province_code: item for item in records}
        self.assertEqual(set(by_code.keys()), {"TPHCM", "DT"})

        # TPHCM appeared on both 2026-11-16 and 2026-11-14; newest must win
        hcm = by_code["TPHCM"]
        self.assertEqual(hcm.draw_date, "2026-11-16")
        self.assertEqual(hcm.prizes.giai8, ("05",))
        self.assertEqual(hcm.prizes.dac_biet, ("012345",))

    def test_sync_from_xsmn_mobi_respects_only_if_newer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_lottery.db"

            # Pre-seed DT with a newer date than SAMPLE_HTML (2026-11-23 > 2026-11-16)
            upsert_result(
                LotterySyncInput(
                    province_code="DT",
                    draw_date="2026-11-23",
                    prizes=XsmnPrizes(
                        giai8=("88",),
                        giai7=("888",),
                        giai6=("8881", "8882", "8883"),
                        giai5=("8884",),
                        giai4=("80001", "80002", "80003", "80004", "80005", "80006", "80007"),
                        giai3=("81111", "82222"),
                        giai2=("83333",),
                        giai1=("84444",),
                        dac_biet=("855555",),
                    ),
                ),
                db_path=db_path,
            )

            with patch("lotto_store.scraper.fetch_xsmn_html", return_value=SAMPLE_HTML):
                summary = sync_from_xsmn_mobi(db_path=db_path, only_if_newer=True)

            self.assertEqual(summary.parsed_count, 2)
            self.assertEqual(summary.synced_count, 1)
            self.assertEqual(len(summary.skipped_older), 1)
            self.assertIn("DT", summary.skipped_older[0])

            stored_hcm = get_result_by_province("TPHCM", db_path=db_path)
            self.assertIsNotNone(stored_hcm)
            assert stored_hcm is not None
            self.assertEqual(stored_hcm.draw_date, "2026-11-16")

            stored_dt = get_result_by_province("DT", db_path=db_path)
            self.assertIsNotNone(stored_dt)
            assert stored_dt is not None
            self.assertEqual(stored_dt.draw_date, "2026-11-23")
            self.assertEqual(len(get_all_results(db_path=db_path)), 2)

            # Verify automatic JSON export alongside db_path
            expected_json = db_path.with_suffix(".json")
            self.assertEqual(summary.export_json_path, expected_json)
            self.assertTrue(expected_json.exists())
            exported = json.loads(expected_json.read_text(encoding="utf-8"))
            self.assertEqual(exported["totalProvinces"], 2)
            self.assertEqual(
                [item["provinceCode"] for item in exported["results"]],
                ["DT", "TPHCM"],
            )

    def test_sync_from_xsmn_mobi_dry_run_skips_json_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_lottery.db"
            json_path = Path(tmp_dir) / "custom_export.json"

            with patch("lotto_store.scraper.fetch_xsmn_html", return_value=SAMPLE_HTML):
                summary = sync_from_xsmn_mobi(
                    db_path=db_path,
                    dry_run=True,
                    export_json_path=json_path,
                )

            self.assertIsNone(summary.export_json_path)
            self.assertFalse(json_path.exists())


if __name__ == "__main__":
    unittest.main()
