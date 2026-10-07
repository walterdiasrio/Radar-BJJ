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

document.querySelectorAll(".btn-assinar").forEach(btn => {
  btn.addEventListener("click", () => iniciarCheckout(btn.dataset.plano, btn.dataset.periodicidade));
});

// --- PIX (Asaas) -----------------------------------------------------------
const elModalPix = document.getElementById("modal-pix");
const elStatusPix = document.getElementById("status-pix");
const elPixNome = document.getElementById("pix-nome");
const elPixCpf = document.getElementById("pix-cpf");
const elBtnGerarPix = document.getElementById("btn-gerar-pix");
let pixPlanoAtual = null;
let pixPeriodicidadeAtual = null;

function mostrarStatusPix(texto, ehErro = false) {
  elStatusPix.textContent = texto;
  elStatusPix.className = "status-importacao" + (ehErro ? " erro" : "");
}

function abrirModalPix(plano, periodicidade) {
  pixPlanoAtual = plano;
  pixPeriodicidadeAtual = periodicidade;
  elPixNome.value = "";
  elPixCpf.value = "";
  mostrarStatusPix("");
  elModalPix.style.display = "flex";
}

document.getElementById("btn-fechar-pix").addEventListener("click", () => {
  elModalPix.style.display = "none";
});
elModalPix.addEventListener("click", (ev) => {
  if (ev.target === elModalPix) elModalPix.style.display = "none";
});

document.querySelectorAll(".btn-pagar-pix").forEach(btn => {
  btn.addEventListener("click", () => abrirModalPix(btn.dataset.plano, btn.dataset.periodicidade));
});

elBtnGerarPix.addEventListener("click", async () => {
  const nome = elPixNome.value.trim();
  const cpf = elPixCpf.value.replace(/\D/g, "");
  if (!nome || !cpf) {
    mostrarStatusPix("Preencha nome e CPF.", true);
    return;
  }
  mostrarStatusPix("Gerando cobrança PIX...");
  try {
    const resp = await fetchAutenticado("/api/checkout-pix", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plano: pixPlanoAtual, periodicidade: pixPeriodicidadeAtual, cpf, nome }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui gerar a cobrança");
    window.location.href = dados.url;
  } catch (err) {
    mostrarStatusPix(`Erro: ${err.message}`, true);
  }
});

document.querySelectorAll(".btn-teste-gratis-pix").forEach(btn => {
  btn.addEventListener("click", async () => {
    mostrarStatus("Liberando teste grátis...");
    try {
      const resp = await fetchAutenticado("/api/teste-gratis-pix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plano: btn.dataset.plano }),
      });
      const dados = await resp.json();
      if (!resp.ok) throw new Error(dados.erro || "não consegui liberar o teste grátis");
      window.location.reload();
    } catch (err) {
      mostrarStatus(`Erro: ${err.message}`, true);
    }
  });
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
