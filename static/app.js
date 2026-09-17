const $ = (id) => document.getElementById(id);

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

async function loadDashboard() {
  try {
    const [auctions, lots, sales, revenue] = await Promise.all([
      api("/api/auctions"), api("/api/lots"), api("/api/sales"), api("/api/reports/revenue")
    ]);
    $("auction-count").textContent = auctions.length;
    $("lot-count").textContent = lots.length;
    $("sale-count").textContent = sales.length;
    $("revenue").textContent = Number(revenue.revenue).toFixed(2);

    $("auctions").innerHTML = auctions.map(a => `
      <div class="item">
        <b>#${a.id} ${a.name}</b><span>Статус: ${a.status}</span>
        <div class="actions">
          ${a.status === "PLANNED" ? `<button onclick="changeAuction(${a.id}, 'start')">Запустить</button>` : ""}
          ${a.status === "ACTIVE" ? `<button onclick="changeAuction(${a.id}, 'finish')">Завершить</button>` : ""}
        </div>
      </div>`).join("") || "Нет аукционов";

    $("lots").innerHTML = lots.map(l => `
      <div class="item"><b>#${l.id} ${l.name}</b>
      <span>Аукцион #${l.auction_id}, стартовая цена ${Number(l.starting_price).toFixed(2)}, статус ${l.status}</span></div>
    `).join("") || "Нет лотов";

    $("sales").innerHTML = sales.map(s => `
      <div class="item"><b>Продажа #${s.id}</b>
      <span>Лот #${s.lot_id}, покупатель #${s.buyer_id}, цена ${Number(s.price).toFixed(2)}</span></div>
    `).join("") || "Нет продаж";
  } catch (error) {
    message(error.message, true);
  }
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

loadDashboard();
