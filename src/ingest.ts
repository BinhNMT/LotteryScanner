import { pathToFileURL } from "node:url";
import type Database from "better-sqlite3";
import { openLotteryDb } from "./db.js";
import { XSMN_PROVINCES, type XsmnProvinceCode } from "./provinces.js";
import { DEFAULT_EXPORT_JSON_PATH, exportLatestResultsToJson } from "./queries.js";
import type { LotterySyncInput, XsmnPrizes } from "./types.js";

/**
 * Atomically overwrites the latest lottery state for one or more provinces.
 * Uses SQLite INSERT OR REPLACE so no historical rows are retained.
 */
export function syncLatestLotteryResults(
  db: Database.Database,
  results: LotterySyncInput[]
): number {
  const upsertStmt = db.prepare<{
    province_code: string;
    draw_date: string;
    prizes: string;
    updated_at: string;
  }>(`
    INSERT OR REPLACE INTO latest_lottery_results (
      province_code,
      draw_date,
      prizes,
      updated_at
    ) VALUES (
      @province_code,
      @draw_date,
      @prizes,
      @updated_at
    )
  `);

  const nowIso = new Date().toISOString();

  const runBatch = db.transaction((items: LotterySyncInput[]) => {
    for (const item of items) {
      upsertStmt.run({
        province_code: item.provinceCode.trim().toUpperCase(),
        draw_date: item.drawDate,
        prizes: JSON.stringify(item.prizes),
        updated_at: nowIso,
      });
    }
    return items.length;
  });

  return runBatch(results);
}

/**
 * Overwrites latest lottery results in SQLite and immediately exports
 * the full database snapshot to JSON for static web UI consumption.
 */
export function syncAndExportLatestLotteryResults(
  db: Database.Database,
  results: LotterySyncInput[],
  outputPath: string = DEFAULT_EXPORT_JSON_PATH
): { syncedCount: number; exportPath: string } {
  const syncedCount = syncLatestLotteryResults(db, results);
  const exportPath = exportLatestResultsToJson(db, outputPath);
  return { syncedCount, exportPath };
}

/**
 * Generates deterministic, format-valid sample prizes for seeding all 21 provinces.
 */
function buildSamplePrizes(seed: number): XsmnPrizes {
  const pad = (n: number, len: number) => String(Math.abs(n) % 10 ** len).padStart(len, "0");
  const s = seed + 1;
  return {
    giai8: [pad(s * 17, 2)],
    giai7: [pad(s * 137, 3)],
    giai6: [pad(s * 1021, 4), pad(s * 2039, 4), pad(s * 3049, 4)],
    giai5: [pad(s * 4127, 4)],
    giai4: [
      pad(s * 11003, 5),
      pad(s * 22013, 5),
      pad(s * 33023, 5),
      pad(s * 44029, 5),
      pad(s * 55049, 5),
      pad(s * 66067, 5),
      pad(s * 77081, 5),
    ],
    giai3: [pad(s * 15101, 5), pad(s * 29207, 5)],
    giai2: [pad(s * 41309, 5)],
    giai1: [pad(s * 53411, 5)],
    dacBiet: [pad(s * 104729, 6)],
  };
}

// Latest draw date per province for a full weekly cycle (2026-11-11 .. 2026-11-17)
const LATEST_DRAW_DATE_BY_PROVINCE: Record<XsmnProvinceCode, string> = {
  BT: "2026-11-17",
  VT: "2026-11-17",
  BL: "2026-11-17",
  TPHCM: "2026-11-16",
  DT: "2026-11-16",
  CM: "2026-11-16",
  TG: "2026-11-15",
  KG: "2026-11-15",
  DL: "2026-11-15",
  LA: "2026-11-14",
  BP: "2026-11-14",
  HG: "2026-11-14",
  VL: "2026-11-13",
  BD: "2026-11-13",
  TV: "2026-11-13",
  TN: "2026-11-12",
  AG: "2026-11-12",
  BTH: "2026-11-12",
  DN: "2026-11-11",
  CT: "2026-11-11",
  ST: "2026-11-11",
};

const isMain =
  Boolean(process.argv[1]) && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  const db = openLotteryDb();
  try {
    const allProvincesBatch: LotterySyncInput[] = XSMN_PROVINCES.map((province, index) => ({
      provinceCode: province.code,
      drawDate: LATEST_DRAW_DATE_BY_PROVINCE[province.code],
      prizes: buildSamplePrizes(index),
    }));

    const { syncedCount, exportPath } = syncAndExportLatestLotteryResults(
      db,
      allProvincesBatch
    );
    console.log(`Synced ${syncedCount} province(s) into latest_lottery_results.`);
    console.log(`Exported JSON snapshot to ${exportPath}.`);
  } finally {
    db.close();
  }
}
