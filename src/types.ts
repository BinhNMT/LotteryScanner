import type { XsmnProvinceCode } from "./provinces.js";

/**
 * Prize tiers for Xổ số kiến thiết miền Nam (Giải 8 -> Giải Đặc Biệt).
 * Values are strings to preserve leading zeros (e.g. "05", "004192").
 */
export interface XsmnPrizes {
  giai8: [string]; // 1 x 2 digits
  giai7: [string]; // 1 x 3 digits
  giai6: [string, string, string]; // 3 x 4 digits
  giai5: [string]; // 1 x 4 digits
  giai4: [string, string, string, string, string, string, string]; // 7 x 5 digits
  giai3: [string, string]; // 2 x 5 digits
  giai2: [string]; // 1 x 5 digits
  giai1: [string]; // 1 x 5 digits
  dacBiet: [string]; // 1 x 6 digits
}

export interface LotterySyncInput {
  provinceCode: XsmnProvinceCode;
  drawDate: string; // YYYY-MM-DD
  prizes: XsmnPrizes;
}

export interface LatestLotteryRow {
  province_code: string;
  draw_date: string;
  prizes: string;
  updated_at: string;
}

export interface LatestLotteryResult {
  provinceCode: string;
  drawDate: string;
  prizes: XsmnPrizes;
  updatedAt: string;
}

export interface ExportedLotteryResult extends LatestLotteryResult {
  provinceName: string;
  drawDays: readonly number[];
}

export interface LotteryExportPayload {
  exportedAt: string;
  totalProvinces: number;
  results: ExportedLotteryResult[];
}

