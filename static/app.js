const $ = (id) => document.getElementById(id);
const esc = (value) => String(value).replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));
const money = (value) => Number(value).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

async function api(path, options = {}) {
  const response = await fetch(path, { headers: {"Content-Type": "application/json"}, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

// Всплывающие уведомления: показываются поверх страницы и сами пропадают через 4с,
// вместо статичного блока, который раньше всегда занимал место внизу страницы.
function toast(text, type = "success") {
  const container = $("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = text;
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 250);
  }, 4000);
}

function optionList(items, labelFn) {
  return items.map((i) => `<option value="${i.id}">${esc(labelFn(i))}</option>`).join("");
}

let state = { auctions: [], sellers: [], buyers: [], lots: [], sales: [] };

async function loadDashboard() {
  try {
    const [auctions, sellers, buyers, lots, sales, revenue] = await Promise.all([
      api("/api/auctions"), api("/api/sellers"), api("/api/buyers"),
      api("/api/lots"), api("/api/sales"), api("/api/reports/revenue"),
    ]);
    state = { auctions, sellers, buyers, lots, sales };

    $("auction-count").textContent = auctions.length;
    $("lot-count").textContent = lots.length;
    $("sale-count").textContent = sales.length;
    $("revenue").textContent = money(revenue.revenue);

    renderAuctions();
    renderPeople();
    renderLotForm();
    renderLots();
    renderSales();
  } catch (error) {
    toast(error.message, "error");
  }
}

function renderAuctions() {
  $("auctions").innerHTML = state.auctions.map(a => `
    <div class="item">
      <b>#${a.id} ${esc(a.name)}</b><span class="tag tag-${a.status}">${a.status}</span>
      <div class="actions">
        ${a.status === "PLANNED" ? `<button onclick="changeAuction(${a.id}, 'start')">Запустить</button>` : ""}
        ${a.status === "ACTIVE" ? `<button onclick="changeAuction(${a.id}, 'finish')">Завершить</button>` : ""}
        ${["PLANNED", "ACTIVE"].includes(a.status) ? `<button class="danger" onclick="changeAuction(${a.id}, 'cancel')">Отменить</button>` : ""}
      </div>
    </div>`).join("") || "Нет аукционов";
}

function renderPeople() {
  $("sellers").innerHTML = state.sellers.map(s => `
    <tr><td class="id-cell">#${s.id}</td><td>${esc(s.name)}</td><td>${esc(s.email)}</td><td>${esc(s.phone || "—")}</td></tr>
  `).join("") || `<tr><td class="empty-row" colspan="4">Нет продавцов</td></tr>`;
  $("buyers").innerHTML = state.buyers.map(b => `
    <tr><td class="id-cell">#${b.id}</td><td>${esc(b.name)}</td><td>${esc(b.email)}</td><td>${esc(b.phone || "—")}</td></tr>
  `).join("") || `<tr><td class="empty-row" colspan="4">Нет покупателей</td></tr>`;
}

function renderLotForm() {
  const auctionSelect = document.querySelector("#lot-form select[name=auction_id]");
  const sellerSelect = document.querySelector("#lot-form select[name=seller_id]");
  const openAuctions = state.auctions.filter(a => a.status === "PLANNED" || a.status === "ACTIVE");
  auctionSelect.innerHTML = optionList(openAuctions, a => `#${a.id} ${a.name} (${a.status})`) || "<option disabled>Нет доступных аукционов</option>";
  sellerSelect.innerHTML = optionList(state.sellers, s => `#${s.id} ${s.name}`) || "<option disabled>Нет продавцов</option>";
}

function lotSaleInfo(lotId) {
  const sale = state.sales.find(s => s.lot_id === lotId);
  if (!sale) return "";
  const buyer = state.buyers.find(b => b.id === sale.buyer_id);
  return `Продан ${buyer ? esc(buyer.name) : "покупателю #" + sale.buyer_id} за ${money(sale.price)} ₽`;
}

function renderLots() {
  const buyerOptions = optionList(state.buyers, b => `#${b.id} ${b.name}`);
  const auctionName = (id) => {
    const a = state.auctions.find(x => x.id === id);
    return a ? `#${a.id} ${esc(a.name)}` : `#${id}`;
  };
  const sellerName = (id) => {
    const s = state.sellers.find(x => x.id === id);
    return s ? `#${s.id} ${esc(s.name)}` : `#${id}`;
  };

  $("lots").innerHTML = state.lots.map(l => {
    const auction = state.auctions.find(a => a.id === l.auction_id);
    const auctionActive = auction && auction.status === "ACTIVE";
    const mainRow = `
      <tr>
        <td class="id-cell">#${l.id}</td>
        <td>${esc(l.name)}</td>
        <td><span class="tag tag-${l.status}">${l.status}</span></td>
        <td>${auctionName(l.auction_id)}</td>
        <td>${sellerName(l.seller_id)}</td>
        <td class="price-cell">${money(l.starting_price)}</td>
        <td class="price-cell" id="lot-current-price-${l.id}">${money(l.current_price)}</td>
      </tr>`;

    let controls;
    if (l.status === "SOLD") {
      controls = `<div class="hint">${lotSaleInfo(l.id)}</div>`;
    } else if (l.status === "UNSOLD") {
      controls = `<div class="hint">Не продан: аукцион завершён или отменён</div>`;
    } else if (!auctionActive) {
      controls = `<div class="hint">Ставки и продажа доступны только для ACTIVE аукциона</div>`;
    } else if (!state.buyers.length) {
      controls = `<div class="hint">Добавьте покупателя, чтобы делать ставки и оформлять продажу</div>`;
    } else {
      controls = `
        <div class="sub-form">
          <span class="sub-label">Ставка:</span>
          <select id="bid-buyer-${l.id}">${buyerOptions}</select>
          <input id="bid-amount-${l.id}" type="number" step="0.01" min="0.01" placeholder="Сумма, ₽ (мин. шаг 100)">
          <button class="secondary" onclick="placeBid(${l.id})">Сделать ставку</button>
          <button class="secondary" onclick="toggleBids(${l.id})">История ставок</button>
        </div>
        <div class="sub-form">
          <span class="sub-label">Продажа:</span>
          <select id="sale-buyer-${l.id}">${buyerOptions}</select>
          <input id="sale-price-${l.id}" type="number" step="0.01" min="0.01" placeholder="Цена продажи, ₽">
          <button onclick="createSale(${l.id})">Оформить продажу</button>
        </div>
        <div class="bids-list" id="bids-${l.id}"></div>
      `;
    }
    const controlsRow = `<tr class="lot-controls-row"><td colspan="7">${controls}</td></tr>`;
    return mainRow + controlsRow;
  }).join("") || `<tr><td class="empty-row" colspan="7">Нет лотов</td></tr>`;
}

function renderSales() {
  const buyerName = (id) => {
    const b = state.buyers.find(x => x.id === id);
    return b ? `#${b.id} ${esc(b.name)}` : `#${id}`;
  };
  $("sales").innerHTML = state.sales.map(s => `
    <tr>
      <td class="id-cell">#${s.id}</td>
      <td>#${s.lot_id}</td>
      <td>${buyerName(s.buyer_id)}</td>
      <td class="price-cell">${money(s.price)}</td>
    </tr>
  `).join("") || `<tr><td class="empty-row" colspan="4">Нет продаж</td></tr>`;
}

async function toggleBids(lotId) {
  const box = $(`bids-${lotId}`);
  if (box.dataset.open === "1") {
    box.innerHTML = "";
    box.dataset.open = "0";
    return;
  }
  try {
    const bids = await api(`/api/lots/${lotId}/bids`);
    box.dataset.open = "1";
    box.innerHTML = bids.length
      ? "Ставки: " + bids.map(b => `#${b.buyer_id} — ${money(b.amount)} ₽`).join(", ")
      : "Ставок пока нет";
  } catch (error) { toast(error.message, "error"); }
}

async function placeBid(lotId) {
  const buyerId = Number($(`bid-buyer-${lotId}`).value);
  const amount = $(`bid-amount-${lotId}`).value;
  if (!amount) return toast("Укажите сумму ставки", "error");
  try {
    await api(`/api/lots/${lotId}/bids`, {
      method: "POST",
      body: JSON.stringify({ buyer_id: buyerId, amount }),
    });
    toast("Ставка принята");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
}

async function createSale(lotId) {
  const buyerId = Number($(`sale-buyer-${lotId}`).value);
  const price = $(`sale-price-${lotId}`).value;
  if (!price) return toast("Укажите цену продажи", "error");
  try {
    await api("/api/sales", {
      method: "POST",
      body: JSON.stringify({ lot_id: lotId, buyer_id: buyerId, price }),
    });
    toast("Продажа оформлена, лот закрыт");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
}

async function changeAuction(id, action) {
  try {
    await api(`/api/auctions/${id}/${action}`, {method: "POST"});
    toast("Статус аукциона изменен");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
}

$("auction-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    await api("/api/auctions", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"),
        description: form.get("description") || null,
        start_at: new Date(form.get("start_at")).toISOString(),
        end_at: new Date(form.get("end_at")).toISOString()
      })
    });
    event.target.reset();
    toast("Аукцион создан");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
});

$("seller-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    await api("/api/sellers", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"), email: form.get("email"), phone: form.get("phone") || null,
      }),
    });
    event.target.reset();
    toast("Продавец добавлен");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
});

$("buyer-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    await api("/api/buyers", {
      method: "POST",
      body: JSON.stringify({
        name: form.get("name"), email: form.get("email"), phone: form.get("phone") || null,
      }),
    });
    event.target.reset();
    toast("Покупатель добавлен");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
});

$("lot-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    await api("/api/lots", {
      method: "POST",
      body: JSON.stringify({
        auction_id: Number(form.get("auction_id")),
        seller_id: Number(form.get("seller_id")),
        name: form.get("name"),
        description: form.get("description") || null,
        starting_price: form.get("starting_price"),
      }),
    });
    event.target.reset();
    toast("Лот добавлен");
    await loadDashboard();
  } catch (error) { toast(error.message, "error"); }
});

loadDashboard();
