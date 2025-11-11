const API = {
  get: async (path) => {
    const resp = await fetch(path);
    if (!resp.ok) throw new Error(await resp.text());
    return resp.json();
  },
  post: async (path, payload) => {
    const resp = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.error || "Error desconocido");
    }
    return data;
  },
};

const elements = {
  chain: document.getElementById("chain-table"),
  peers: document.getElementById("peer-table"),
  history: document.getElementById("history-table"),
  walletList: document.getElementById("wallet-list"),
  senderSelect: document.getElementById("sender-select"),
  txForm: document.getElementById("tx-form"),
  txFeedback: document.getElementById("tx-feedback"),
  createWalletBtn: document.getElementById("create-wallet"),
  refreshBtn: document.getElementById("refresh-button"),
};

const statusEls = {
  chain: document.getElementById("stat-chain"),
  mempool: document.getElementById("stat-mempool"),
  peers: document.getElementById("stat-peers"),
  updated: document.getElementById("stat-updated"),
};

const renderTable = (target, headers, rows) => {
  const template = document
    .getElementById("table-template")
    .content.cloneNode(true);
  const table = template.querySelector("table");
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  thead.innerHTML = `<tr>${headers
    .map((h) => `<th>${h}</th>`)
    .join("")}</tr>`;
  tbody.innerHTML = rows
    .map((cols) => `<tr>${cols.map((c) => `<td>${c}</td>`).join("")}</tr>`)
    .join("");
  target.innerHTML = "";
  target.appendChild(table);
};

const formatTimestamp = (ts) => {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString();
};

async function refreshHealth() {
  const data = await API.get("/health");
  statusEls.chain.textContent = data.chain_length;
  statusEls.mempool.textContent = data.mempool_size;
  statusEls.peers.textContent = `${data.peers.activos}/${data.peers.total}`;
  statusEls.updated.textContent = new Date().toLocaleTimeString();
}

async function refreshWallets() {
  const data = await API.get("/wallets");
  const wallets = data.wallets || [];
  elements.walletList.innerHTML = wallets
    .map(
      (wallet) => `<article class="wallet-card">
        <div class="label">${wallet.label}</div>
        <div class="address">${wallet.address}</div>
        <div class="balance">${wallet.balance} Ð</div>
      </article>`
    )
    .join("");
  elements.senderSelect.innerHTML = wallets
    .map(
      (wallet) =>
        `<option value="${wallet.address}">${wallet.label} (${wallet.balance} Ð)</option>`
    )
    .join("");
}

async function refreshChain() {
  const data = await API.get("/chain?limit=8");
  const rows = (data.blocks || []).map((block) => [
    `#${block.index}`,
    block.transactions.length,
    block.miner_address.slice(0, 10) + "…",
    block.block_hash.slice(0, 12) + "…",
    formatTimestamp(block.timestamp),
  ]);
  renderTable(elements.chain, ["Bloque", "Txs", "Minero", "Hash", "Fecha"], rows);
}

async function refreshPeers() {
  const data = await API.get("/peers");
  const rows = (data.peers || []).map((peer) => [
    peer.peer_id.slice(0, 8) + "…",
    peer.address,
    peer.activo
      ? '<span class="badge success">activo</span>'
      : '<span class="badge muted">offline</span>',
    peer.ultimo_contacto ? formatTimestamp(peer.ultimo_contacto) : "-",
  ]);
  renderTable(elements.peers, ["Peer", "Dirección", "Estado", "Último contacto"], rows);
}

async function refreshHistory() {
  const data = await API.get("/transactions/history?limit=25");
  const rows = (data.transactions || []).map((tx) => [
    tx.tx_id ? tx.tx_id.slice(0, 10) + "…" : "-",
    tx.sender
      ? tx.sender.slice(0, 10) + "…"
      : '<span class="badge muted">GENESIS</span>',
    tx.recipient ? tx.recipient.slice(0, 10) + "…" : "-",
    `${tx.amount || 0} Ð`,
    `#${tx.block_index}`,
    formatTimestamp(tx.timestamp),
  ]);
  renderTable(
    elements.history,
    ["Tx", "Emisor", "Receptor", "Monto", "Bloque", "Fecha"],
    rows
  );
}

async function refreshDashboard() {
  try {
    await Promise.all([
      refreshHealth(),
      refreshWallets(),
      refreshChain(),
      refreshPeers(),
      refreshHistory(),
    ]);
  } catch (error) {
    console.error(error);
  }
}

elements.txForm.addEventListener("submit", async (evt) => {
  evt.preventDefault();
  elements.txFeedback.textContent = "";
  elements.txFeedback.className = "feedback";
  try {
    const form = new FormData(elements.txForm);
    const payload = {
      recipient: form.get("recipient"),
      amount: parseFloat(form.get("amount") || "0"),
      sender_address: form.get("sender"),
    };
    const result = await API.post("/transactions", payload);
    elements.txFeedback.textContent = `Transacción ${result.tx_id.slice(
      0,
      10
    )} enviada correctamente.`;
    elements.txFeedback.classList.add("success");
    elements.txForm.reset();
    await refreshDashboard();
  } catch (error) {
    elements.txFeedback.textContent = error.message;
    elements.txFeedback.classList.add("error");
  }
});

elements.createWalletBtn.addEventListener("click", async () => {
  const label = prompt("Nombre de la wallet:");
  if (label === null) return;
  try {
    await API.post("/wallets", { label: label.trim() || "wallet" });
    await refreshDashboard();
  } catch (error) {
    alert(error.message);
  }
});

elements.refreshBtn.addEventListener("click", refreshDashboard);

setInterval(refreshDashboard, 7000);
refreshDashboard();
