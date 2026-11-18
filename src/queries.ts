import { mkdirSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import type Database from "better-sqlite3";
import { XSMN_PROVINCE_MAP, type XsmnProvinceCode } from "./provinces.js";
import type {
  ExportedLotteryResult,
  LatestLotteryResult,
  LatestLotteryRow,
  LotteryExportPayload,
  XsmnPrizes,
} from "./types.js";

export const DEFAULT_EXPORT_JSON_PATH = resolve(process.cwd(), "lottery_latest.json");

/**
 * Fetches the latest state for all active provinces in a single table read.
 * Because the table holds at most ~21 Southern provinces (1 row each),
 * the entire dataset fits on a single SQLite B-tree page.
 */
export function getAllLatestResults(db: Database.Database): LatestLotteryResult[] {
  const stmt = db.prepare<[], LatestLotteryRow>(`
    SELECT province_code, draw_date, prizes, updated_at
    FROM latest_lottery_results
    ORDER BY draw_date DESC, province_code ASC
  `);

  return stmt.all().map((row) => ({
    provinceCode: row.province_code,
    drawDate: row.draw_date,
    prizes: JSON.parse(row.prizes) as XsmnPrizes,
    updatedAt: row.updated_at,
  }));
}

/**
 * Fetches the latest state for a single province via its clustered primary key.
 */
export function getLatestResultByProvince(
  db: Database.Database,
  provinceCode: string
): LatestLotteryResult | null {
  const stmt = db.prepare<[string], LatestLotteryRow>(`
    SELECT province_code, draw_date, prizes, updated_at
    FROM latest_lottery_results
    WHERE province_code = ?
  `);

  const row = stmt.get(provinceCode.trim().toUpperCase());
  if (!row) return null;

  return {
    provinceCode: row.province_code,
    drawDate: row.draw_date,
    prizes: JSON.parse(row.prizes) as XsmnPrizes,
    updatedAt: row.updated_at,
  };
}

/**
 * Builds a static-UI-friendly JSON payload from the current database state.
 */
export function buildExportPayload(db: Database.Database): LotteryExportPayload {
  const rows = getAllLatestResults(db);
  const results: ExportedLotteryResult[] = rows.map((row) => {
    const meta = XSMN_PROVINCE_MAP[row.provinceCode as XsmnProvinceCode];
    return {
      provinceCode: row.provinceCode,
      provinceName: meta ? meta.name : row.provinceCode,
      drawDays: meta ? [...meta.drawDays] : [],
      drawDate: row.drawDate,
      updatedAt: row.updatedAt,
      prizes: row.prizes,
    };
  });

  return {
    exportedAt: new Date().toISOString(),
    totalProvinces: results.length,
    results,
  };
}

/**
 * Atomically exports the entire `latest_lottery_results` table to a JSON file
 * for static web UI consumption.
 */
export function exportLatestResultsToJson(
  db: Database.Database,
  outputPath: string = DEFAULT_EXPORT_JSON_PATH
): string {
  const targetPath = resolve(outputPath);
  mkdirSync(dirname(targetPath), { recursive: true });

  const payload = buildExportPayload(db);
  const serialized = `${JSON.stringify(payload, null, 2)}\n`;
  const tempPath = `${targetPath}.${process.pid}.tmp`;

  try {
    writeFileSync(tempPath, serialized, "utf8");
    renameSync(tempPath, targetPath);
  } catch (err) {
    try {
      unlinkSync(tempPath);
    } catch {
      // Ignore cleanup error if temp file was not created
    }
    throw err;
  }

  return targetPath;
}

