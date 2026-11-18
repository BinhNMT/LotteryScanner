import type Database from "better-sqlite3";
import type { LatestLotteryResult, LatestLotteryRow, XsmnPrizes } from "./types.js";

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

