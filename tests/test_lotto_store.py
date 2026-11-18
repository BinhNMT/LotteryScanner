"""Unit tests for `lotto_store` Read/Write/Query/Delete interfaces."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from lotto_store import (
    LotterySyncInput,
    XsmnPrizes,
    clear_all_results,
    count_results,
    delete_result_by_province,
    delete_results_by_date,
    export_results_to_json,
    get_all_results,
    get_result_by_province,
    lottery_db_session,
    query_results,
    sync_results,
    upsert_result,
)


def _sample_prizes(g8: str = "05", dac_biet: str = "004192") -> XsmnPrizes:
    return XsmnPrizes(
        giai8=(g8,),
        giai7=("037",),
        giai6=("0123", "4567", "8901"),
        giai5=("0456",),
        giai4=("01234", "12345", "23456", "34567", "45678", "56789", "67890"),
        giai3=("09876", "54321"),
        giai2=("11223",),
        giai1=("44556",),
        dac_biet=(dac_biet,),
    )


class TestLottoStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp_dir.name) / "test_lottery.db"

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def test_upsert_and_latest_state_overwrite(self) -> None:
        first = upsert_result(
            LotterySyncInput(
                province_code=" tphcm ",
                draw_date="2026-11-14",
                prizes=_sample_prizes(g8="05", dac_biet="004192"),
            ),
            db_path=self.db_path,
        )
        self.assertEqual(first.province_code, "TPHCM")
        self.assertEqual(count_results(db_path=self.db_path), 1)

        # Overwrite same province with newer draw_date -> still only 1 row
        upsert_result(
            {
                "province_code": "TPHCM",
                "draw_date": "2026-11-16",
                "prizes": _sample_prizes(g8="09", dac_biet="099999").to_dict(),
            },
            db_path=self.db_path,
        )
        self.assertEqual(count_results(db_path=self.db_path), 1)

        fetched = get_result_by_province("tphcm", db_path=self.db_path)
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.draw_date, "2026-11-16")
        self.assertEqual(fetched.prizes.giai8, ("09",))
        self.assertEqual(fetched.prizes.dac_biet, ("099999",))

    def test_json_format_matches_typescript_schema(self) -> None:
        prizes = _sample_prizes(g8="05", dac_biet="004192")
        parsed = json.loads(prizes.to_json())
        self.assertIn("dacBiet", parsed)
        self.assertEqual(parsed["giai8"], ["05"])
        self.assertEqual(parsed["dacBiet"], ["004192"])

    def test_sync_read_query_and_delete_lifecycle(self) -> None:
        with lottery_db_session(self.db_path) as conn:
            written = sync_results(
                [
                    LotterySyncInput("TPHCM", "2026-11-16", _sample_prizes(g8="05", dac_biet="004192")),
                    LotterySyncInput("DT", "2026-11-16", _sample_prizes(g8="12", dac_biet="123405")),
                    LotterySyncInput("BT", "2026-11-17", _sample_prizes(g8="88", dac_biet="888888")),
                ],
                conn=conn,
            )
            self.assertEqual(written, 3)

            all_rows = get_all_results(conn=conn)
            self.assertEqual([r.province_code for r in all_rows], ["BT", "DT", "TPHCM"])

            # Query by draw_date
            nov16 = query_results(draw_date="2026-11-16", conn=conn)
            self.assertEqual([r.province_code for r in nov16], ["DT", "TPHCM"])

            # Query by draw_day (1 = Monday -> TPHCM, DT)
            monday = query_results(draw_day=1, conn=conn)
            self.assertEqual([r.province_code for r in monday], ["DT", "TPHCM"])

            # Query by exact number and suffix
            exact = query_results(search_number="004192", match_mode="exact", conn=conn)
            self.assertEqual([r.province_code for r in exact], ["TPHCM"])

            suffix_05 = query_results(search_number="05", match_mode="suffix", conn=conn)
            self.assertEqual([r.province_code for r in suffix_05], ["DT", "TPHCM"])

            # Delete by province
            self.assertTrue(delete_result_by_province("BT", conn=conn))
            self.assertFalse(delete_result_by_province("BT", conn=conn))
            self.assertEqual(count_results(conn=conn), 2)

            # Delete by date
            deleted_date = delete_results_by_date("2026-11-16", conn=conn)
            self.assertEqual(deleted_date, 2)
            self.assertEqual(count_results(conn=conn), 0)

            # Clear all
            sync_results(
                [LotterySyncInput("KG", "2026-11-15", _sample_prizes())],
                conn=conn,
            )
            self.assertEqual(clear_all_results(conn=conn), 1)
            self.assertEqual(count_results(conn=conn), 0)

    def test_validation_rejects_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            LotterySyncInput("INVALID", "2026-11-16", _sample_prizes())

        with self.assertRaises(ValueError):
            LotterySyncInput("TPHCM", "16-11-2026", _sample_prizes())

        with self.assertRaises(ValueError):
            XsmnPrizes(
                giai8=("5",),  # must be 2 digits
                giai7=("037",),
                giai6=("0123", "4567", "8901"),
                giai5=("0456",),
                giai4=("01234", "12345", "23456", "34567", "45678", "56789", "67890"),
                giai3=("09876", "54321"),
                giai2=("11223",),
                giai1=("44556",),
                dac_biet=("004192",),
            )

    def test_export_results_to_json_and_auto_export_on_sync(self) -> None:
        json_path = Path(self._tmp_dir.name) / "nested" / "lottery_latest.json"

        sync_results(
            [
                LotterySyncInput("TPHCM", "2026-11-16", _sample_prizes(g8="05", dac_biet="004192")),
                LotterySyncInput("BT", "2026-11-17", _sample_prizes(g8="09", dac_biet="012345")),
            ],
            db_path=self.db_path,
            export_json_path=json_path,
        )

        self.assertTrue(json_path.exists())
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("exportedAt", payload)
        self.assertEqual(payload["totalProvinces"], 2)
        self.assertEqual([item["provinceCode"] for item in payload["results"]], ["BT", "TPHCM"])

        bt = payload["results"][0]
        self.assertEqual(bt["provinceName"], "Bến Tre")
        self.assertEqual(bt["drawDays"], [2])
        self.assertEqual(bt["drawDate"], "2026-11-17")
        self.assertEqual(bt["prizes"]["giai8"], ["09"])
        self.assertEqual(bt["prizes"]["dacBiet"], ["012345"])

        # Direct export_results_to_json after upsert
        upsert_result(
            LotterySyncInput("DT", "2026-11-16", _sample_prizes(g8="12", dac_biet="123405")),
            db_path=self.db_path,
        )
        export_results_to_json(json_path, db_path=self.db_path)
        updated_payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_payload["totalProvinces"], 3)
        self.assertEqual(
            [item["provinceCode"] for item in updated_payload["results"]],
            ["BT", "DT", "TPHCM"],
        )


if __name__ == "__main__":
    unittest.main()
