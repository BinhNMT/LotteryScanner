/**
 * Quy tắc dò vé số kiến thiết miền Nam (XSMN - vé 6 chữ số).
 */

export const PRIZE_ROWS = [
  { key: "giai8", label: "Giải Tám", digits: 2, rewardVnd: 100_000 },
  { key: "giai7", label: "Giải Bảy", digits: 3, rewardVnd: 200_000 },
  { key: "giai6", label: "Giải Sáu", digits: 4, rewardVnd: 400_000 },
  { key: "giai5", label: "Giải Năm", digits: 4, rewardVnd: 1_000_000 },
  { key: "giai4", label: "Giải Tư", digits: 5, rewardVnd: 3_000_000 },
  { key: "giai3", label: "Giải Ba", digits: 5, rewardVnd: 10_000_000 },
  { key: "giai2", label: "Giải Nhì", digits: 5, rewardVnd: 15_000_000 },
  { key: "giai1", label: "Giải Nhất", digits: 5, rewardVnd: 30_000_000 },
  { key: "dacBiet", label: "Đặc Biệt", digits: 6, rewardVnd: 2_000_000_000 },
];

const SPECIAL_SUB_REWARD_VND = 50_000_000;
const CONSOLATION_REWARD_VND = 6_000_000;

/**
 * Chuẩn hóa chuỗi nhập mã số dự thưởng: chỉ giữ ký tự số, tối đa 6 ký tự.
 */
export function sanitizeTicketInput(rawValue) {
  return String(rawValue ?? "").replace(/\D/g, "").slice(0, 6);
}

/**
 * Kiểm tra hợp lệ mã số dự thưởng XSMN (đủ 6 chữ số).
 */
export function isValidTicketNumber(ticketNumber) {
  return /^\d{6}$/.test(ticketNumber);
}

/**
 * Định dạng ngày YYYY-MM-DD sang DD/MM/YYYY.
 */
export function formatDateVi(isoDate) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(isoDate ?? ""))) {
    return String(isoDate ?? "");
  }
  const [year, month, day] = isoDate.split("-");
  return `${day}/${month}/${year}`;
}

/**
 * Định dạng số tiền VNĐ.
 */
export function formatVnd(amount) {
  return `${new Intl.NumberFormat("vi-VN").format(amount)} đ`;
}

/**
 * Kiểm tra xem vé có trúng Giải Khuyến Khích XSMN hay không:
 * Trùng chữ số đầu tiên của Giải Đặc Biệt và chỉ sai đúng 1 chữ số trong 5 số còn lại.
 */
function isConsolationMatch(ticketNumber, specialPrize) {
  if (ticketNumber.length !== 6 || specialPrize.length !== 6) {
    return false;
  }
  if (ticketNumber[0] !== specialPrize[0]) {
    return false;
  }
  let diffCount = 0;
  for (let i = 1; i < 6; i += 1) {
    if (ticketNumber[i] !== specialPrize[i]) {
      diffCount += 1;
    }
  }
  return diffCount === 1;
}

/**
 * Dò vé số 6 chữ số với bảng giải thưởng của một đài XSMN.
 * Trả về danh sách các giải trúng, tổng tiền thưởng và tập số trúng để tô sáng trên bảng.
 */
export function checkXsmnTicket(ticketNumber, prizes) {
  if (!isValidTicketNumber(ticketNumber)) {
    throw new Error("Mã số dự thưởng phải gồm đúng 6 chữ số.");
  }

  const matches = [];
  const matchedPrizeNumbers = new Set();

  for (const row of PRIZE_ROWS) {
    const numbers = Array.isArray(prizes?.[row.key]) ? prizes[row.key] : [];
    const ticketTail = ticketNumber.slice(-row.digits);

    for (const winningNumber of numbers) {
      if (String(winningNumber) === ticketTail) {
        matches.push({
          prizeKey: row.key,
          prizeLabel: row.label,
          winningNumber: String(winningNumber),
          rewardVnd: row.rewardVnd,
        });
        matchedPrizeNumbers.add(`${row.key}:${winningNumber}`);
      }
    }
  }

  const specialList = Array.isArray(prizes?.dacBiet) ? prizes.dacBiet : [];
  for (const rawSpecial of specialList) {
    const special = String(rawSpecial);
    if (special.length !== 6 || ticketNumber === special) {
      continue;
    }

    if (ticketNumber.slice(1) === special.slice(1)) {
      matches.push({
        prizeKey: "phuDacBiet",
        prizeLabel: "Giải Phụ Đặc Biệt",
        winningNumber: special,
        rewardVnd: SPECIAL_SUB_REWARD_VND,
        note: "Trùng 5 số cuối của Giải Đặc Biệt",
      });
      matchedPrizeNumbers.add(`dacBiet:${special}`);
    } else if (isConsolationMatch(ticketNumber, special)) {
      matches.push({
        prizeKey: "khuyenKhich",
        prizeLabel: "Giải Khuyến Khích",
        winningNumber: special,
        rewardVnd: CONSOLATION_REWARD_VND,
        note: "Trùng số đầu và chỉ sai 1 số trong 5 số cuối của Giải Đặc Biệt",
      });
      matchedPrizeNumbers.add(`dacBiet:${special}`);
    }
  }

  const totalRewardVnd = matches.reduce((sum, item) => sum + item.rewardVnd, 0);

  return {
    ticketNumber,
    isWinner: matches.length > 0,
    matches,
    totalRewardVnd,
    matchedPrizeNumbers,
  };
}
