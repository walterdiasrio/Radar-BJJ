async function carregarDestaques() {
  const elDestaques = document.getElementById("destaques");
  if (!elDestaques) return;
  try {
    const resp = await fetch("/api/noticias");
    const lista = await resp.json();
    if (!lista.length) {
      elDestaques.innerHTML = "";
      return;
    }
    elDestaques.innerHTML = `
      <img src="/img/banner-noticias.jpg" alt="BJJ News" class="destaques-titulo-banner">
      <div class="destaques-grade">
        ${lista.map((n, i) => `
          <div class="destaque-card" data-indice="${i}">
            <img src="${n.imagem_url}" alt="${n.manchete}">
            <div class="destaque-manchete">${n.manchete}</div>
          </div>
        `).join("")}
      </div>
    `;
    elDestaques.querySelectorAll(".destaque-card").forEach(card => {
      const noticia = lista[Number(card.dataset.indice)];
      card.addEventListener("click", () => abrirNoticiaModal(noticia.imagem_url, noticia.manchete, noticia.texto));
    });
  } catch (err) {
    elDestaques.innerHTML = "";
  }
}

function badgeStatusAgenda(status) {
  return status === "inscrito"
    ? '<span class="badge-inscricao badge-aberta">Inscrição Confirmada</span>'
    : '<span class="badge-inscricao badge-desconhecida">Tenho Interesse</span>';
}

function renderizarProximasHome(itens) {
  const elCard = document.getElementById("home-proximas-competicoes");
  const elLista = document.getElementById("lista-proximas-home");
  if (!itens.length) {
    elCard.style.display = "none";
    return;
  }
  elCard.style.display = "block";
  elLista.innerHTML = itens.map(item => `
    <div class="cartao-alerta">
      <div class="cartao-alerta-topo">
        <div>
          <div class="cartao-alerta-federacao">${item.federacao} — ${item.nome}</div>
          <div class="cartao-alerta-filtros">${item.data}${item.local ? " · " + item.local : ""}</div>
        </div>
      </div>
      <div style="margin-top:8px;">${badgeStatusAgenda(item.status)}</div>
    </div>
  `).join("");
}

function renderizarMedalhasHome(medalhas) {
  const elCard = document.getElementById("home-quadro-medalhas");
  elCard.style.display = "block";
  document.getElementById("grade-medalhas-home").innerHTML = `
    <div class="stat-box"><div class="stat-value">🥇 ${medalhas.ouros}</div><div class="stat-label">Ouros</div></div>
    <div class="stat-box"><div class="stat-value">🥈 ${medalhas.pratas}</div><div class="stat-label">Pratas</div></div>
    <div class="stat-box"><div class="stat-value">🥉 ${medalhas.bronzes}</div><div class="stat-label">Bronzes</div></div>
  `;
}

async function ajustarCartaoBoasVindas() {
  const elBotoesLogado = document.getElementById("home-botoes-logado");
  const elCtaCadastro = document.getElementById("home-cta-cadastro");
  const elTitulo = document.getElementById("home-titulo");
  const elSubtituloNome = document.getElementById("home-subtitulo-nome");
  const elTextoMarketing = document.getElementById("home-texto-marketing");
  if (!elBotoesLogado || !elCtaCadastro) return;

  let dadosSessao;
  try {
    const resp = await fetch("/api/sessao");
    dadosSessao = await resp.json();
  } catch (err) {
    return;
  }

  if (!dadosSessao.logado) {
    elBotoesLogado.style.display = "none";
    elCtaCadastro.style.display = "block";
    return;
  }

  elCtaCadastro.style.display = "none";
  elTextoMarketing.style.display = "none";
  elTitulo.style.display = "none";

  let resumo;
  try {
    const resp = await fetch("/api/home-resumo");
    resumo = await resp.json();
  } catch (err) {
    return;
  }

  elSubtituloNome.textContent = `Bem-vindo(a) de volta, ${resumo.nome}! 👋`;
  elSubtituloNome.style.display = "block";

  renderizarProximasHome(resumo.proximas_competicoes || []);

  if (!resumo.tem_assinatura) {
    elBotoesLogado.style.display = "none";
    return;
  }

  elBotoesLogado.style.display = "block";
  const elBotaoBuscaRapida = document.getElementById("home-botao-busca-rapida");
  if (resumo.tem_filtro_salvo) {
    elBotaoBuscaRapida.innerHTML = '<a href="/buscador?auto=1"><button type="button">Buscar Atleta com meu filtro salvo</button></a>';
  } else {
    elBotaoBuscaRapida.innerHTML = '<a href="/buscador"><button type="button">Ir para o Radar de Atletas</button></a>';
  }

  if (resumo.medalhas) {
    renderizarMedalhasHome(resumo.medalhas);
  }
}

carregarDestaques();
ajustarCartaoBoasVindas();
