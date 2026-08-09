// ---------- Abas internas ----------
document.querySelectorAll(".tab-carreira-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-carreira-btn").forEach(b => b.classList.remove("ativo"));
    document.querySelectorAll(".tab-carreira-content").forEach(c => c.classList.remove("ativo"));
    btn.classList.add("ativo");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("ativo");
    if (btn.dataset.tab === "historico") carregarHistorico();
    if (btn.dataset.tab === "estatisticas") carregarEstatisticas();
  });
});

function mostrarStatus(elId, texto, ehErro = false) {
  const el = document.getElementById(elId);
  el.textContent = texto;
  el.className = "status-importacao" + (ehErro ? " erro" : "");
}

// ---------- Perfil ----------
async function carregarPerfil() {
  try {
    const resp = await fetchAutenticado("/api/carreira/perfil");
    const p = await resp.json();
    document.getElementById("p_nome").value = p.nome || "";
    document.getElementById("p_faixa").value = p.faixa || "Branca";
    document.getElementById("p_grau").value = p.grau || "0";
    document.getElementById("p_categoria").value = p.categoria || "";
    document.getElementById("p_academia").value = p.academia || "";
    document.getElementById("p_inicio").value = p.inicio || "";
  } catch (err) {
    // segue com os campos vazios
  }
}

document.getElementById("form-perfil").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = {
    nome: document.getElementById("p_nome").value,
    faixa: document.getElementById("p_faixa").value,
    grau: document.getElementById("p_grau").value,
    categoria: document.getElementById("p_categoria").value,
    academia: document.getElementById("p_academia").value,
    inicio: document.getElementById("p_inicio").value,
  };
  try {
    const resp = await fetchAutenticado("/api/carreira/perfil", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    if (!resp.ok) throw new Error("não consegui salvar o perfil");
    mostrarStatus("status-perfil", "Perfil salvo! 🥋");
  } catch (err) {
    mostrarStatus("status-perfil", `Erro: ${err.message}`, true);
  }
});

// ---------- Registrar ----------
const lutasContainer = document.getElementById("lutas-container");
const templateLutaRow = document.getElementById("template-luta-row");

function addLutaRow(luta) {
  const frag = templateLutaRow.content.cloneNode(true);
  const row = frag.querySelector(".luta-row");
  if (luta) {
    row.querySelector(".luta-adversario").value = luta.adversario || "";
    row.querySelector(".luta-resultado").value = luta.resultado || "vitoria";
    row.querySelector(".luta-metodo").value = luta.metodo || "pontos";
  }
  row.querySelector(".btn-remove-luta").addEventListener("click", () => row.remove());
  lutasContainer.appendChild(row);
}

document.getElementById("btn-add-luta").addEventListener("click", () => addLutaRow());

function resetFormCompeticao() {
  document.getElementById("form-competicao").reset();
  document.getElementById("e_editing_id").value = "";
  document.getElementById("e_pais").value = "Brasil";
  lutasContainer.innerHTML = "";
  addLutaRow();
  document.getElementById("btn-salvar-competicao").textContent = "Salvar Registro";
  document.getElementById("btn-cancelar-edicao").classList.add("hidden");
  document.getElementById("e_data").valueAsDate = new Date();
}

document.getElementById("btn-cancelar-edicao").addEventListener("click", resetFormCompeticao);

document.getElementById("form-competicao").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const editingId = document.getElementById("e_editing_id").value;
  const lutas = [...lutasContainer.querySelectorAll(".luta-row")].map(row => ({
    adversario: row.querySelector(".luta-adversario").value,
    resultado: row.querySelector(".luta-resultado").value,
    metodo: row.querySelector(".luta-metodo").value,
  }));
  const dados = {
    data: document.getElementById("e_data").value,
    campeonato: document.getElementById("e_campeonato").value,
    categoria: document.getElementById("e_categoria").value,
    pais: document.getElementById("e_pais").value || "Brasil",
    medalha: document.getElementById("e_medalha").value || null,
    lutas,
  };

  try {
    const resp = editingId
      ? await fetchAutenticado(`/api/carreira/competicoes/${editingId}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados),
        })
      : await fetchAutenticado("/api/carreira/competicoes", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados),
        });
    const resultado = await resp.json();
    if (!resp.ok) throw new Error(resultado.erro || "não consegui salvar");

    mostrarStatus("status-competicao", editingId ? "Competição atualizada! 🥋" : "Competição salva! 🥋");
    resetFormCompeticao();
    carregarHistorico();
  } catch (err) {
    mostrarStatus("status-competicao", `Erro: ${err.message}`, true);
  }
});

function irParaAbaRegistrar(competicao) {
  document.getElementById("e_editing_id").value = competicao.id;
  document.getElementById("e_data").value = competicao.data || "";
  document.getElementById("e_campeonato").value = competicao.campeonato || "";
  document.getElementById("e_categoria").value = competicao.categoria || "";
  document.getElementById("e_pais").value = competicao.pais || "Brasil";
  document.getElementById("e_medalha").value = competicao.medalha || "";
  lutasContainer.innerHTML = "";
  (competicao.lutas || []).forEach(l => addLutaRow(l));
  if (!competicao.lutas || competicao.lutas.length === 0) addLutaRow();

  document.getElementById("btn-salvar-competicao").textContent = "Atualizar Registro";
  document.getElementById("btn-cancelar-edicao").classList.remove("hidden");

  document.querySelectorAll(".tab-carreira-btn").forEach(b => b.classList.remove("ativo"));
  document.querySelectorAll(".tab-carreira-content").forEach(c => c.classList.remove("ativo"));
  document.querySelector('.tab-carreira-btn[data-tab="registrar"]').classList.add("ativo");
  document.getElementById("tab-registrar").classList.add("ativo");
}

async function removerCompeticao(id) {
  if (!confirm("Excluir esta competição (e todas as lutas dela)?")) return;
  try {
    const resp = await fetchAutenticado(`/api/carreira/competicoes/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    carregarHistorico();
  } catch (err) {
    mostrarStatus("status-competicao", `Erro ao remover: ${err.message}`, true);
  }
}

// ---------- Cards ----------
const RESULTADO_LABEL = { vitoria: "Vitória", derrota: "Derrota", empate: "Empate" };
const METODO_LABEL = { pontos: "Pontos", finalizacao: "Finalização", wo: "W.O.", desclassificacao: "Desclassificação", medica: "Médica" };
const MEDALHA_LABEL = { ouro: "🥇 Ouro", prata: "🥈 Prata", bronze: "🥉 Bronze" };

function formatarData(data) {
  if (!data) return "";
  const iso = data.includes("T") ? data : data + "T00:00:00";
  return new Date(iso).toLocaleDateString("pt-BR");
}

function cardCompeticao(c, competicoesPorId) {
  let tags = "";
  if (c.medalha) tags += `<span class="tag-carreira medalha-${c.medalha}">${MEDALHA_LABEL[c.medalha]}</span>`;
  if (c.pais && c.pais !== "Brasil") tags += `<span class="tag-carreira pais">🌎 ${c.pais}</span>`;
  const metaPartes = [formatarData(c.data)];
  if (c.categoria) metaPartes.push(c.categoria);
  const lutasHtml = (c.lutas || []).map(l => `
    <div class="luta-item">
      <span class="tag-carreira ${l.resultado}">${RESULTADO_LABEL[l.resultado]}</span>
      ${l.adversario ? "vs " + l.adversario : ""}${l.metodo ? " · " + METODO_LABEL[l.metodo] : ""}
    </div>`).join("");
  return `
    <div class="cartao-alerta">
      <div class="cartao-alerta-topo">
        <div>
          <h3>${tags}${c.campeonato || "Competição"}</h3>
          <div class="cartao-alerta-federacao">${metaPartes.join(" · ")}</div>
        </div>
        <div style="display:flex; gap: 6px; flex-shrink: 0;">
          <button type="button" class="btn-secundario btn-editar" data-id="${c.id}">Editar</button>
          <button type="button" class="btn-remover" data-id="${c.id}">Remover</button>
        </div>
      </div>
      <div class="lutas-list">${lutasHtml}</div>
    </div>`;
}

function ligarBotoesCard(container, competicoes) {
  container.querySelectorAll(".btn-editar").forEach(btn => {
    btn.addEventListener("click", () => {
      const c = competicoes.find(comp => comp.id === Number(btn.dataset.id));
      if (c) irParaAbaRegistrar(c);
    });
  });
  container.querySelectorAll(".btn-remover").forEach(btn => {
    btn.addEventListener("click", () => removerCompeticao(Number(btn.dataset.id)));
  });
}

// ---------- Histórico ----------
async function carregarHistorico() {
  const el = document.getElementById("lista-historico");
  try {
    const resp = await fetchAutenticado("/api/carreira/competicoes");
    const competicoes = await resp.json();
    if (!competicoes.length) {
      el.innerHTML = '<p style="color:#7c8894;">Nenhum registro ainda. Vai lá registrar sua primeira competição!</p>';
      return;
    }
    el.innerHTML = competicoes.map(c => cardCompeticao(c)).join("");
    ligarBotoesCard(el, competicoes);
  } catch (err) {
    el.innerHTML = `<p class="erro">Erro ao carregar: ${err.message}</p>`;
  }
}

// ---------- Pesquisa ----------
document.getElementById("form-pesquisa").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const params = new URLSearchParams({
    campeonato: document.getElementById("s_campeonato").value,
    adversario: document.getElementById("s_adversario").value,
    de: document.getElementById("s_de").value,
    ate: document.getElementById("s_ate").value,
  });
  const elContagem = document.getElementById("contagem-pesquisa");
  const elLista = document.getElementById("lista-pesquisa");
  try {
    const resp = await fetchAutenticado(`/api/carreira/competicoes?${params}`);
    const competicoes = await resp.json();
    elContagem.textContent = `${competicoes.length} resultado(s)`;
    elLista.innerHTML = competicoes.length
      ? competicoes.map(c => cardCompeticao(c)).join("")
      : '<p style="color:#7c8894;">Nenhuma competição encontrada com esses filtros.</p>';
    ligarBotoesCard(elLista, competicoes);
  } catch (err) {
    elContagem.textContent = "";
    elLista.innerHTML = `<p class="erro">Erro: ${err.message}</p>`;
  }
});

document.getElementById("btn-limpar-pesquisa").addEventListener("click", () => {
  document.getElementById("form-pesquisa").reset();
  document.getElementById("contagem-pesquisa").textContent = "";
  document.getElementById("lista-pesquisa").innerHTML = "";
});

// ---------- Estatísticas ----------
async function carregarEstatisticas() {
  try {
    const resp = await fetchAutenticado("/api/carreira/estatisticas");
    const s = await resp.json();

    const stats = [
      { label: "Competições", value: s.competicoes },
      { label: "Lutas", value: s.lutas },
      { label: "Vitórias", value: s.vitorias },
      { label: "Derrotas", value: s.derrotas },
      { label: "Empates", value: s.empates },
      { label: "Taxa de vitória", value: s.taxa_vitoria + "%" },
      { label: "Sequência atual", value: s.sequencia_atual },
      { label: "Melhor sequência", value: s.melhor_sequencia },
      { label: "🥇 Ouros", value: s.ouros },
      { label: "🥈 Pratas", value: s.pratas },
      { label: "🥉 Bronzes", value: s.bronzes },
    ];
    document.getElementById("grade-estatisticas").innerHTML = stats.map(item => `
      <div class="stat-box">
        <div class="stat-value">${item.value}</div>
        <div class="stat-label">${item.label}</div>
      </div>`).join("");

    desenharGrafico(s.grafico || []);
  } catch (err) {
    document.getElementById("grade-estatisticas").innerHTML = `<p class="erro">Erro: ${err.message}</p>`;
  }
}

function desenharGrafico(pontos) {
  const svg = document.getElementById("grafico-evolucao");
  const W = 600, H = 240, PAD = 30;
  if (!pontos.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="#888" font-size="14">Sem competições registradas ainda</text>`;
    return;
  }

  const maxY = Math.max(...pontos.map(p => p.vitorias_acumuladas), 1);
  const maxX = Math.max(pontos.length - 1, 1);
  const escalaX = i => PAD + (i / maxX) * (W - 2 * PAD);
  const escalaY = y => H - PAD - (y / maxY) * (H - 2 * PAD);

  const pathD = pontos.map((p, i) => `${i === 0 ? "M" : "L"} ${escalaX(i)} ${escalaY(p.vitorias_acumuladas)}`).join(" ");
  const cores = { vitoria: "#4caf50", derrota: "#ef5350", empate: "#f9a825" };
  const pontosSvg = pontos.map((p, i) =>
    `<circle cx="${escalaX(i)}" cy="${escalaY(p.vitorias_acumuladas)}" r="4" fill="${cores[p.resultado]}" />`
  ).join("");

  svg.innerHTML = `
    <line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}" stroke="#888" stroke-width="1"/>
    <line x1="${PAD}" y1="${PAD}" x2="${PAD}" y2="${H - PAD}" stroke="#888" stroke-width="1"/>
    <path d="${pathD}" fill="none" stroke="#4caf50" stroke-width="2"/>
    ${pontosSvg}
    <text x="${PAD}" y="${H - 8}" font-size="11" fill="#888">Início</text>
    <text x="${W - PAD}" y="${H - 8}" font-size="11" fill="#888" text-anchor="end">Hoje</text>
    <text x="${PAD - 6}" y="${PAD + 4}" font-size="11" fill="#888" text-anchor="end">${maxY}</text>
  `;
}

// ---------- Init ----------
addLutaRow();
document.getElementById("e_data").valueAsDate = new Date();
carregarPerfil();
