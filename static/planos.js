const elStatus = document.getElementById("status");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
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

async function iniciar() {
  let logado = false;
  try {
    const resp = await fetch("/api/sessao");
    const dados = await resp.json();
    logado = !!dados.logado;
  } catch (err) {
    // segue tratando como visitante
  }

  // Botões "Assinar" dos cards de texto (com preço/benefícios reais).
  document.querySelectorAll(".btn-assinar").forEach(btn => {
    btn.addEventListener("click", () => {
      const plano = btn.dataset.plano;
      const periodicidade = btn.dataset.periodicidade;
      if (logado) {
        iniciarCheckout(plano, periodicidade);
      } else {
        window.location.href = `/cadastro?plano=${plano}&periodicidade=${periodicidade}`;
      }
    });
  });

  const btnFree = document.querySelector(".btn-plano-free");
  if (btnFree) {
    btnFree.addEventListener("click", () => {
      window.location.href = logado ? btnFree.dataset.hrefLogado : btnFree.dataset.hrefVisitante;
    });
  }

  // Banners de imagem (mesma ação dos botões acima, como atalho visual).
  document.querySelectorAll(".plano-card-banner[data-plano]").forEach(link => {
    link.addEventListener("click", (ev) => {
      if (!logado) return; // deixa o navegador seguir o href pro /cadastro
      ev.preventDefault();
      iniciarCheckout(link.dataset.plano, link.dataset.periodicidade);
    });
  });

  const bannerFree = document.getElementById("banner-plano-free");
  if (bannerFree) {
    bannerFree.addEventListener("click", (ev) => {
      if (!logado) return;
      ev.preventDefault();
      window.location.href = bannerFree.dataset.hrefLogado;
    });
  }
}

iniciar();
