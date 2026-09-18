const $ = (id) => document.getElementById(id);
const esc = (value) => String(value).replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));

async function api(path, options = {}) {
  const response = await fetch(path, { headers: {"Content-Type": "application/json"}, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);
  return data;
}

function message(text, error = false) {
  const box = $("message");
  box.textContent = text;
  box.className = error ? "error" : "success";
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
    $("revenue").textContent = Number(revenue.revenue).toFixed(2);

    renderAuctions();
    renderPeople();
    renderLotForm();
    renderLots();
    renderSales();
  } catch (error) {
    message(error.message, true);
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
  $("sellers").innerHTML = state.sellers.map(s => `<div class="item">#${s.id} ${esc(s.name)} <span>${esc(s.email)}</span></div>`).join("") || "Нет продавцов";
  $("buyers").innerHTML = state.buyers.map(b => `<div class="item">#${b.id} ${esc(b.name)} <span>${esc(b.email)}</span></div>`).join("") || "Нет покупателей";
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
  return ` — продан ${buyer ? esc(buyer.name) : "покупателю #" + sale.buyer_id} за ${Number(sale.price).toFixed(2)}`;
}

function renderLots() {
  const buyerOptions = optionList(state.buyers, b => `#${b.id} ${b.name}`);
  $("lots").innerHTML = state.lots.map(l => {
    const auction = state.auctions.find(a => a.id === l.auction_id);
    const auctionActive = auction && auction.status === "ACTIVE";
    let sub = "";
    if (l.status === "SOLD") {
      sub = `<div class="hint">${lotSaleInfo(l.id)}</div>`;
    } else if (l.status === "UNSOLD") {
      sub = `<div class="hint">Не продан: аукцион завершён или отменён</div>`;
    } else if (!auctionActive) {
      sub = `<div class="hint">Ставки и продажа доступны только для ACTIVE аукциона</div>`;
    } else if (!state.buyers.length) {
      sub = `<div class="hint">Добавьте покупателя, чтобы делать ставки и оформлять продажу</div>`;
    } else {
      sub = `
        <div class="sub-form">
          <select id="bid-buyer-${l.id}">${buyerOptions}</select>
          <input id="bid-amount-${l.id}" type="number" step="0.01" min="0.01" placeholder="Сумма ставки">
          <button class="secondary" onclick="placeBid(${l.id})">Сделать ставку</button>
          <button class="secondary" onclick="toggleBids(${l.id})">Ставки</button>
        </div>
        <div class="sub-form">
          <select id="sale-buyer-${l.id}">${buyerOptions}</select>
          <input id="sale-price-${l.id}" type="number" step="0.01" min="0.01" placeholder="Цена продажи">
          <button onclick="createSale(${l.id})">Оформить продажу</button>
        </div>
        <div class="bids-list" id="bids-${l.id}"></div>
      `;
    }
    return `
      <div class="item"><b>#${l.id} ${esc(l.name)}</b>
      <span class="tag tag-${l.status}">${l.status}</span>
      <span>Аукцион #${l.auction_id}, продавец #${l.seller_id}, стартовая цена ${Number(l.starting_price).toFixed(2)}</span>
      ${sub}</div>
    `;
  }).join("") || "Нет лотов";
}

function renderSales() {
  $("sales").innerHTML = state.sales.map(s => `
    <div class="item"><b>Продажа #${s.id}</b>
    <span>Лот #${s.lot_id}, покупатель #${s.buyer_id}, цена ${Number(s.price).toFixed(2)}</span></div>
  `).join("") || "Нет продаж";
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
      ? "Ставки: " + bids.map(b => `#${b.buyer_id} — ${Number(b.amount).toFixed(2)}`).join(", ")
      : "Ставок пока нет";
  } catch (error) { message(error.message, true); }
}

async function placeBid(lotId) {
  const buyerId = Number($(`bid-buyer-${lotId}`).value);
  const amount = $(`bid-amount-${lotId}`).value;
  if (!amount) return message("Укажите сумму ставки", true);
  try {
    await api(`/api/lots/${lotId}/bids`, {
      method: "POST",
      body: JSON.stringify({ buyer_id: buyerId, amount }),
    });
    message("Ставка принята");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
}

async function createSale(lotId) {
  const buyerId = Number($(`sale-buyer-${lotId}`).value);
  const price = $(`sale-price-${lotId}`).value;
  if (!price) return message("Укажите цену продажи", true);
  try {
    await api("/api/sales", {
      method: "POST",
      body: JSON.stringify({ lot_id: lotId, buyer_id: buyerId, price }),
    });
    message("Продажа оформлена, лот закрыт");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
}

async function changeAuction(id, action) {
  try {
    await api(`/api/auctions/${id}/${action}`, {method: "POST"});
    message("Статус аукциона изменен");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
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
    message("Аукцион создан");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
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
    message("Продавец добавлен");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
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
    message("Покупатель добавлен");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
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
    message("Лот добавлен");
    await loadDashboard();
  } catch (error) { message(error.message, true); }
});

loadDashboard();
