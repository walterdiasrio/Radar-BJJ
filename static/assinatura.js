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
  vencida: "vencida",
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

    const ehPix = a.forma_pagamento === "pix";
    let infoVencimento = "";
    if (ehPix && a.periodo_atual_fim) {
      const dataFim = new Date(Number(a.periodo_atual_fim) * 1000);
      const rotulo = a.status === "vencida" ? "Venceu em" : "Vence em";
      infoVencimento = ` · ${rotulo} ${dataFim.toLocaleDateString("pt-BR")}`;
    }
    // PIX não tem portal do Stripe pra gerenciar (não é uma assinatura de
    // verdade lá — ver pagamentos.py) — o botão vira "Renovar com PIX" em
    // vez de "Gerenciar assinatura".
    const botaoGerenciar = ehPix
      ? `<button type="button" id="btn-renovar-pix">Renovar com PIX</button>`
      : `<button type="button" id="btn-gerenciar">Gerenciar assinatura</button>`;

    elAssinaturaAtiva.innerHTML = `
      <div class="plano-card" style="max-width: 420px; margin-bottom: 24px;">
        <h3>Plano atual: ${NOMES_PLANO[a.plano] || a.plano}</h3>
        <p class="plano-desc">
          Status: ${NOMES_STATUS[a.status] || a.status}
          ${a.periodicidade ? ` · cobrança ${a.periodicidade}` : ""}
          ${ehPix ? " · pago por PIX" : ""}${infoVencimento}
        </p>
        ${botaoGerenciar}
      </div>
    `;
    if (ehPix) {
      document.getElementById("btn-renovar-pix").addEventListener("click", () => iniciarCheckoutPix(a.plano, a.periodicidade));
    } else {
      document.getElementById("btn-gerenciar").addEventListener("click", abrirPortal);
    }

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

async function iniciarCheckout(plano, periodicidade) {
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
}

async function iniciarCheckoutPix(plano, periodicidade) {
  mostrarStatus("Preparando o pagamento no PIX...");
  try {
    const resp = await fetchAutenticado("/api/checkout-pix", {
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
}

document.querySelectorAll(".btn-assinar").forEach(btn => {
  btn.addEventListener("click", () => iniciarCheckout(btn.dataset.plano, btn.dataset.periodicidade));
});

document.querySelectorAll(".btn-pix").forEach(btn => {
  btn.addEventListener("click", () => iniciarCheckoutPix(btn.dataset.plano, btn.dataset.periodicidade));
});

async function autoIniciarCheckoutSeVeioDoCadastro() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("auto") !== "1") return;
  const plano = params.get("plano");
  const periodicidade = params.get("periodicidade");
  if (!plano || !periodicidade) return;
  const btn = document.querySelector(`.btn-assinar[data-plano="${plano}"][data-periodicidade="${periodicidade}"]`);
  if (btn && !btn.disabled) iniciarCheckout(plano, periodicidade);
}

carregarAssinaturaAtual().then(autoIniciarCheckoutSeVeioDoCadastro);
