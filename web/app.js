import {
  PRIZE_ROWS,
  checkXsmnTicket,
  formatDateVi,
  formatVnd,
  isValidTicketNumber,
  sanitizeTicketInput,
} from "./checker.js";

const DATA_URL = "./lottery_latest.json";

const state = {
  exportedAt: null,
  results: [],
  byProvince: new Map(),
  lastMatchedSet: new Set(),
};

const dom = {
  dataMeta: document.getElementById("data-meta"),
  form: document.getElementById("check-form"),
  ticketInput: document.getElementById("ticket-number"),
  clearTicketBtn: document.getElementById("clear-ticket-btn"),
  provinceSelect: document.getElementById("province-select"),
  drawDateInput: document.getElementById("draw-date"),
  chipsContainer: document.getElementById("date-province-chips"),
  chipsList: document.getElementById("chips-list"),
  formError: document.getElementById("form-error"),
  checkResult: document.getElementById("check-result"),
  boardSubtitle: document.getElementById("board-subtitle"),
  boardDateBadge: document.getElementById("board-date-badge"),
  boardNotice: document.getElementById("board-notice"),
  prizeTableBody: document.getElementById("prize-table-body"),
};

function formatDateTimeVi(isoTimestamp) {
  if (!isoTimestamp) return "";
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return new Intl.DateTimeFormat("vi-VN", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function showFormError(message) {
  dom.formError.textContent = message;
  dom.formError.hidden = false;
}

function clearFormError() {
  dom.formError.hidden = true;
  dom.formError.textContent = "";
}

function clearCheckResult() {
  dom.checkResult.hidden = true;
  dom.checkResult.innerHTML = "";
  state.lastMatchedSet = new Set();
}

function getSelectedProvinceResult() {
  const code = dom.provinceSelect.value;
  return state.byProvince.get(code) ?? null;
}

function populateProvinceSelect(results) {
  dom.provinceSelect.innerHTML = "";

  const sorted = [...results].sort((a, b) =>
    a.provinceName.localeCompare(b.provinceName, "vi")
  );

  for (const item of sorted) {
    const option = document.createElement("option");
    option.value = item.provinceCode;
    option.textContent = `${item.provinceName} (${item.provinceCode}) — ${formatDateVi(item.drawDate)}`;
    dom.provinceSelect.appendChild(option);
  }
}

function renderDateChips(selectedDate) {
  const matching = state.results.filter((item) => item.drawDate === selectedDate);
  if (!selectedDate || matching.length === 0) {
    dom.chipsContainer.hidden = true;
    dom.chipsList.innerHTML = "";
    return;
  }

  dom.chipsContainer.hidden = false;
  dom.chipsList.innerHTML = "";

  const currentCode = dom.provinceSelect.value;
  for (const item of matching) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `chip-btn${item.provinceCode === currentCode ? " is-active" : ""}`;
    btn.textContent = item.provinceName;
    btn.addEventListener("click", () => {
      dom.provinceSelect.value = item.provinceCode;
      clearFormError();
      clearCheckResult();
      renderDateChips(dom.drawDateInput.value);
      renderPrizeBoard();
    });
    dom.chipsList.appendChild(btn);
  }
}

function renderPrizeBoard() {
  const result = getSelectedProvinceResult();
  const selectedDate = dom.drawDateInput.value;

  if (!result) {
    dom.boardSubtitle.textContent = "Chưa chọn tỉnh/thành";
    dom.boardDateBadge.hidden = true;
    dom.boardNotice.hidden = true;
    dom.prizeTableBody.innerHTML = `
      <tr>
        <td class="empty-cell" colspan="2">Vui lòng chọn tỉnh/thành để xem bảng kết quả.</td>
      </tr>
    `;
    return;
  }

  dom.boardSubtitle.textContent = `Đài ${result.provinceName} (${result.provinceCode})`;
  dom.boardDateBadge.textContent = `Kỳ quay ${formatDateVi(result.drawDate)}`;
  dom.boardDateBadge.hidden = false;

  if (selectedDate && selectedDate !== result.drawDate) {
    dom.boardNotice.hidden = false;
    dom.boardNotice.innerHTML = `
      <span>
        Hệ thống chỉ lưu kỳ quay mới nhất. Đài <strong>${result.provinceName}</strong> hiện có kết quả ngày
        <strong>${formatDateVi(result.drawDate)}</strong>, chưa có dữ liệu cho ngày
        <strong>${formatDateVi(selectedDate)}</strong>.
      </span>
      <button type="button" id="sync-latest-date-btn" class="inline-action-btn">
        Chọn ngày ${formatDateVi(result.drawDate)}
      </button>
    `;
    const syncBtn = document.getElementById("sync-latest-date-btn");
    syncBtn?.addEventListener("click", () => {
      dom.drawDateInput.value = result.drawDate;
      clearFormError();
      renderDateChips(result.drawDate);
      renderPrizeBoard();
    });
  } else {
    dom.boardNotice.hidden = true;
    dom.boardNotice.innerHTML = "";
  }

  dom.prizeTableBody.innerHTML = "";
  for (const row of PRIZE_ROWS) {
    const tr = document.createElement("tr");
    if (row.key === "dacBiet") {
      tr.classList.add("row-special");
    }

    const th = document.createElement("th");
    th.scope = "row";
    th.textContent = row.label;

    const td = document.createElement("td");
    const numbersWrap = document.createElement("div");
    numbersWrap.className = "prize-numbers";

    const values = Array.isArray(result.prizes?.[row.key])
      ? result.prizes[row.key]
      : [];

    for (const num of values) {
      const span = document.createElement("span");
      span.className = "prize-num";
      if (state.lastMatchedSet.has(`${row.key}:${num}`)) {
        span.classList.add("is-matched");
      }
      span.textContent = String(num);
      numbersWrap.appendChild(span);
    }

    td.appendChild(numbersWrap);
    tr.appendChild(th);
    tr.appendChild(td);
    dom.prizeTableBody.appendChild(tr);
  }
}

function renderCheckResult(outcome, provinceResult) {
  dom.checkResult.hidden = false;
  state.lastMatchedSet = outcome.matchedPrizeNumbers;

  if (!outcome.isWinner) {
    dom.checkResult.className = "result-panel is-miss";
    dom.checkResult.innerHTML = `
      <div class="result-title">Chúc bạn may mắn lần sau</div>
      <p class="result-desc">
        Vé số <strong class="mono">${outcome.ticketNumber}</strong> không trúng giải nào của đài
        <strong>${provinceResult.provinceName}</strong> kỳ ngày <strong>${formatDateVi(provinceResult.drawDate)}</strong>.
      </p>
    `;
    renderPrizeBoard();
    return;
  }

  const itemsHtml = outcome.matches
    .map(
      (match) => `
      <li>
        <span class="match-prize">${match.prizeLabel}</span>
        <span class="match-meta">
          (Số trúng: <strong class="mono">${match.winningNumber}</strong>${match.note ? ` — ${match.note}` : ""})
        </span>
        <span class="match-reward">${formatVnd(match.rewardVnd)}</span>
      </li>
    `
    )
    .join("");

  dom.checkResult.className = "result-panel is-win";
  dom.checkResult.innerHTML = `
    <div class="result-title">Chúc mừng! Vé của bạn đã trúng thưởng</div>
    <p class="result-desc">
      Vé <strong class="mono">${outcome.ticketNumber}</strong> • Đài <strong>${provinceResult.provinceName}</strong>
      • Ngày <strong>${formatDateVi(provinceResult.drawDate)}</strong>
    </p>
    <ul class="match-list">${itemsHtml}</ul>
    <div class="total-reward">
      Tổng giá trị giải thưởng (trước thuế): <strong>${formatVnd(outcome.totalRewardVnd)}</strong>
    </div>
  `;

  renderPrizeBoard();
}

function handleFormSubmit(event) {
  event.preventDefault();
  clearFormError();

  const sanitized = sanitizeTicketInput(dom.ticketInput.value);
  dom.ticketInput.value = sanitized;

  if (!isValidTicketNumber(sanitized)) {
    clearCheckResult();
    renderPrizeBoard();
    showFormError("Vui lòng nhập đủ 6 chữ số dự thưởng (ví dụ: 094812).");
    dom.ticketInput.focus();
    return;
  }

  const provinceResult = getSelectedProvinceResult();
  if (!provinceResult) {
    clearCheckResult();
    showFormError("Vui lòng chọn tỉnh/thành XSMN.");
    return;
  }

  const selectedDate = dom.drawDateInput.value;
  if (!selectedDate) {
    clearCheckResult();
    showFormError("Vui lòng chọn ngày xổ số.");
    return;
  }

  if (selectedDate !== provinceResult.drawDate) {
    clearCheckResult();
    renderPrizeBoard();
    showFormError(
      `Không có dữ liệu ngày ${formatDateVi(selectedDate)} cho đài ${provinceResult.provinceName}. Dữ liệu mới nhất hiện có là ngày ${formatDateVi(provinceResult.drawDate)}.`
    );
    return;
  }

  const outcome = checkXsmnTicket(sanitized, provinceResult.prizes);
  renderCheckResult(outcome, provinceResult);
}

async function init() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const results = Array.isArray(payload?.results) ? payload.results : [];
    if (results.length === 0) {
      throw new Error("Không có dữ liệu kết quả trong lottery_latest.json.");
    }

    state.exportedAt = payload.exportedAt ?? null;
    state.results = results;
    state.byProvince = new Map(results.map((item) => [item.provinceCode, item]));

    dom.dataMeta.textContent = `Đã tải ${results.length} đài XSMN • Cập nhật lúc ${formatDateTimeVi(state.exportedAt)}`;

    populateProvinceSelect(results);

    const latestFirst = [...results].sort((a, b) =>
      b.drawDate.localeCompare(a.drawDate)
    )[0];
    dom.provinceSelect.value = latestFirst.provinceCode;
    dom.drawDateInput.value = latestFirst.drawDate;

    renderDateChips(latestFirst.drawDate);
    renderPrizeBoard();
  } catch (error) {
    dom.dataMeta.textContent = "Không thể tải lottery_latest.json";
    showFormError(
      `Không thể đọc dữ liệu từ lottery_latest.json (${error.message}). Hãy mở trang qua local web server (ví dụ: python -m http.server).`
    );
    dom.prizeTableBody.innerHTML = `
      <tr>
        <td class="empty-cell" colspan="2">Không tải được bảng kết quả.</td>
      </tr>
    `;
  }
}

dom.ticketInput.addEventListener("input", () => {
  const cleaned = sanitizeTicketInput(dom.ticketInput.value);
  if (dom.ticketInput.value !== cleaned) {
    dom.ticketInput.value = cleaned;
  }
  clearFormError();
});

dom.clearTicketBtn.addEventListener("click", () => {
  dom.ticketInput.value = "";
  clearFormError();
  clearCheckResult();
  renderPrizeBoard();
  dom.ticketInput.focus();
});

dom.provinceSelect.addEventListener("change", () => {
  clearFormError();
  clearCheckResult();
  const result = getSelectedProvinceResult();
  if (result) {
    dom.drawDateInput.value = result.drawDate;
    renderDateChips(result.drawDate);
  }
  renderPrizeBoard();
});

dom.drawDateInput.addEventListener("change", () => {
  clearFormError();
  clearCheckResult();
  const selectedDate = dom.drawDateInput.value;
  renderDateChips(selectedDate);

  const current = getSelectedProvinceResult();
  if (current && current.drawDate !== selectedDate) {
    const firstMatch = state.results.find((item) => item.drawDate === selectedDate);
    if (firstMatch) {
      dom.provinceSelect.value = firstMatch.provinceCode;
      renderDateChips(selectedDate);
    }
  }

  renderPrizeBoard();
});

dom.form.addEventListener("submit", handleFormSubmit);

init();
