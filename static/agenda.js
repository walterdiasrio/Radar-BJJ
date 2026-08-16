const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-agenda");

let itensAtuais = [];

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function badgeStatus(status) {
  return status === "inscrito"
    ? '<span class="badge-inscricao badge-aberta">Inscrição Confirmada</span>'
    : '<span class="badge-inscricao badge-desconhecida">Tenho Interesse</span>';
}

function renderizar(itens) {
  itensAtuais = itens;

  if (!itens.length) {
    elLista.innerHTML = "";
    mostrarStatus('Nenhuma competição marcada ainda. Vá em Competições e marque as que te interessam com "Tenho Interesse" ou "Inscrito".');
    return;
  }
  mostrarStatus(`${itens.length} competição(ões) na agenda.`);

  const blocos = [];
  let atual = null;
  for (const item of itens) {
    if (!atual || atual.mes !== item.mes) {
      atual = { mes: item.mes, itens: [] };
      blocos.push(atual);
    }
    atual.itens.push(item);
  }

  elLista.innerHTML = blocos.map(bloco => `
    <section class="secao-mes">
      <div class="bloco-mes">${bloco.mes} <span class="contagem">(${bloco.itens.length})</span></div>
      ${bloco.itens.map(item => `
        <div class="cartao-alerta">
          <div class="cartao-alerta-topo">
            <div>
              <div class="cartao-alerta-federacao">${item.federacao} — ${item.nome}</div>
              <div class="cartao-alerta-filtros">${item.data}${item.local ? " · " + item.local : ""}</div>
            </div>
            <button type="button" class="btn-remover" data-id="${item.id}">Remover</button>
          </div>
          <div style="margin-top:8px;">${badgeStatus(item.status)}</div>
        </div>
      `).join("")}
    </section>
  `).join("");

  elLista.querySelectorAll(".btn-remover").forEach(btn => {
    btn.addEventListener("click", () => remover(Number(btn.dataset.id)));
  });
}

async function carregar() {
  mostrarStatus("Carregando...");
  try {
    const resp = await fetchAutenticado("/api/agenda");
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar agenda");
    renderizar(dados);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function remover(id) {
  const item = itensAtuais.find(i => i.id === id);
  if (!item) return;
  if (!confirm(`Remover "${item.nome}" da sua agenda?`)) return;

  try {
    const resp = await fetchAutenticado("/api/agenda", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ federacao: item.federacao, nome: item.nome, data: item.data }),
    });
    if (!resp.ok) throw new Error("não consegui remover");
    itensAtuais = itensAtuais.filter(i => i.id !== id);
    renderizar(itensAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregar();
