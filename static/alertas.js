const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-alertas");

const LABEL_FEDERACAO = { cbjj: "CBJJ", fjjrio: "FJJRio", cbjjd: "CBJJD", cbjjo: "CBJJO", cbjje: "CBJJE", fpjj: "FPJJ", adcc: "ADCC", todas: "Todas as federações" };

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

function federacaoLabel(federacao) {
  return federacao.split(",").map(f => LABEL_FEDERACAO[f] || f).join(", ");
}

function resumoFiltros(alerta) {
  const partes = [];
  if (alerta.data_nascimento) partes.push(`nascido(a) ${alerta.data_nascimento.split("-").reverse().join("/")}`);
  if (alerta.genero) partes.push(alerta.genero);
  if (alerta.faixa) partes.push(`faixa ${alerta.faixa}`);
  if (alerta.peso_kg) partes.push(`${alerta.peso_kg} kg (c/ kimono)`);
  if (alerta.peso_sem_kimono) partes.push(`${alerta.peso_sem_kimono} kg (s/ kimono)`);
  if (alerta.nome_atleta) partes.push(`nome contém "${alerta.nome_atleta}"`);
  if (alerta.equipe) partes.push(`equipe contém "${alerta.equipe}"`);
  return partes.length ? partes.join(" · ") : "sem filtros extras";
}

async function carregar() {
  mostrarStatus("Carregando...");
  elLista.innerHTML = "";

  try {
    const resp = await fetchAutenticado("/api/alertas");
    const alertasList = await resp.json();
    if (!resp.ok) throw new Error(alertasList.erro || "erro ao carregar alertas");

    if (!alertasList.length) {
      mostrarStatus("Nenhum alerta criado ainda.");
      return;
    }

    mostrarStatus(`${alertasList.length} alerta(s).`);
    elLista.innerHTML = alertasList.map(a => `
      <div class="cartao-alerta">
        <div class="cartao-alerta-topo">
          <h3>${a.titulo} ${!a.ativo ? '<span class="badge-inscricao badge-desconhecida">Preparando...</span>' : ""}</h3>
          <button class="btn-remover" data-id="${a.id}">Remover</button>
        </div>
        <div class="cartao-alerta-federacao">${federacaoLabel(a.federacao)}</div>
        <div class="cartao-alerta-filtros">${resumoFiltros(a)}</div>
      </div>
    `).join("");

    if (alertasList.some(a => !a.ativo)) {
      setTimeout(carregar, 5000);
    }

    elLista.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => remover(btn.dataset.id));
    });
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function remover(id) {
  if (!confirm("Remover esse alerta?")) return;
  try {
    const resp = await fetchAutenticado(`/api/alertas/${id}`, { method: "DELETE" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao remover");
    carregar();
  } catch (err) {
    mostrarStatus(`Erro ao remover: ${err.message}`, true);
  }
}

carregar();
