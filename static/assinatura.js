const elStatus = document.getElementById("status");
const elAssinaturaAtiva = document.getElementById("assinatura-ativa");
const elPlanosContainer = document.getElementById("planos-container");
const elResumoRadar = document.getElementById("resumo-radar");

const NOMES_PLANO = { atleta: "Atleta PRO", mestre: "Mestre PRO" };
const NOMES_STATUS = {
  trialing: "em teste grátis",
  active: "ativa",
  past_due: "pagamento pendente",
  canceled: "cancelada",
  incomplete: "pendente",
};

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function filtrarPlanoPorPerfil(tipoPerfil) {
  const elAtleta = document.getElementById("plano-card-atleta");
  const elMestre = document.getElementById("plano-card-mestre");
  if (tipoPerfil === "mestre") {
    if (elAtleta) elAtleta.style.display = "none";
  } else {
    if (elMestre) elMestre.style.display = "none";
  }
}

// Não oferece "assinar" pro plano+periodicidade que o usuário já tem
// ativo/em teste — só faz sentido oferecer trocar de plano ou de
// periodicidade (ex: mensal -> anual), não recontratar o que já tem.
function marcarPlanoAtualNosBotoes(a) {
  if (!a || !a.tem_acesso || !a.plano) return;
  document.querySelectorAll(".btn-assinar").forEach(btn => {
    if (btn.dataset.plano === a.plano && btn.dataset.periodicidade === a.periodicidade) {
      btn.disabled = true;
      btn.textContent = "Seu plano atual";
    }
  });
}

async function carregarAssinaturaAtual() {
  try {
    const resp = await fetch("/api/sessao");
    const dados = await resp.json();
    if (!dados.logado) return;

    filtrarPlanoPorPerfil(dados.tipo_perfil);

    const temAcesso = !!(dados.assinatura && dados.assinatura.tem_acesso);
    const veioDoRadar = new URLSearchParams(window.location.search).get("de") === "/buscador";
    if (elResumoRadar) elResumoRadar.style.display = (!temAcesso && veioDoRadar) ? "" : "none";

    if (!dados.assinatura || !dados.assinatura.status) return;

    const a = dados.assinatura;
    marcarPlanoAtualNosBotoes(a);
    elAssinaturaAtiva.style.display = "";
    elAssinaturaAtiva.innerHTML = `
      <div class="plano-card" style="max-width: 420px; margin-bottom: 24px;">
        <h3>Plano atual: ${NOMES_PLANO[a.plano] || a.plano}</h3>
        <p class="plano-desc">
          Status: ${NOMES_STATUS[a.status] || a.status}
          ${a.periodicidade ? ` · cobrança ${a.periodicidade}` : ""}
        </p>
        <button type="button" id="btn-gerenciar">Gerenciar assinatura</button>
      </div>
    `;
    document.getElementById("btn-gerenciar").addEventListener("click", abrirPortal);

    if (a.tem_acesso) {
      elPlanosContainer.querySelector("h2").textContent = "Trocar de plano";
    }
  } catch (err) {
    // segue mostrando só os planos
  }
}

async function abrirPortal() {
  mostrarStatus("Abrindo o gerenciamento de assinatura...");
  try {
    const resp = await fetchAutenticado("/api/portal", { method: "POST" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui abrir o gerenciamento");
    window.location.href = dados.url;
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

document.querySelectorAll(".btn-assinar").forEach(btn => {
  btn.addEventListener("click", async () => {
    const plano = btn.dataset.plano;
    const periodicidade = btn.dataset.periodicidade;
    mostrarStatus("Preparando o pagamento...");
    try {
      const resp = await fetchAutenticado("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plano, periodicidade }),
      });
      const dados = await resp.json();
      if (!resp.ok) throw new Error(dados.erro || "não consegui iniciar o pagamento");
      window.location.href = dados.url;
    } catch (err) {
      mostrarStatus(`Erro: ${err.message}`, true);
    }
  });
});

carregarAssinaturaAtual();
