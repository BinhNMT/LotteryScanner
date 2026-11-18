export interface XsmnProvinceMeta {
  code: XsmnProvinceCode;
  name: string;
  drawDays: readonly number[]; // 0 = Sunday .. 6 = Saturday
}

/**
 * All 21 official provinces/cities in Xổ số kiến thiết miền Nam (XSMN).
 */
export const XSMN_PROVINCES = [
  { code: "TPHCM", name: "TP. Hồ Chí Minh", drawDays: [1, 6] },
  { code: "DT", name: "Đồng Tháp", drawDays: [1] },
  { code: "CM", name: "Cà Mau", drawDays: [1] },
  { code: "BT", name: "Bến Tre", drawDays: [2] },
  { code: "VT", name: "Vũng Tàu", drawDays: [2] },
  { code: "BL", name: "Bạc Liêu", drawDays: [2] },
  { code: "DN", name: "Đồng Nai", drawDays: [3] },
  { code: "CT", name: "Cần Thơ", drawDays: [3] },
  { code: "ST", name: "Sóc Trăng", drawDays: [3] },
  { code: "TN", name: "Tây Ninh", drawDays: [4] },
  { code: "AG", name: "An Giang", drawDays: [4] },
  { code: "BTH", name: "Bình Thuận", drawDays: [4] },
  { code: "VL", name: "Vĩnh Long", drawDays: [5] },
  { code: "BD", name: "Bình Dương", drawDays: [5] },
  { code: "TV", name: "Trà Vinh", drawDays: [5] },
  { code: "LA", name: "Long An", drawDays: [6] },
  { code: "BP", name: "Bình Phước", drawDays: [6] },
  { code: "HG", name: "Hậu Giang", drawDays: [6] },
  { code: "TG", name: "Tiền Giang", drawDays: [0] },
  { code: "KG", name: "Kiên Giang", drawDays: [0] },
  { code: "DL", name: "Đà Lạt", drawDays: [0] },
] as const;

export type XsmnProvinceCode = (typeof XSMN_PROVINCES)[number]["code"];

export const XSMN_PROVINCE_MAP: ReadonlyMap<XsmnProvinceCode, XsmnProvinceMeta> =
  new Map(XSMN_PROVINCES.map((p) => [p.code, p]));

