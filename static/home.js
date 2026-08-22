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

const MEDALHA_EMOJI = { ouro: "🥇", prata: "🥈", bronze: "🥉" };

function formatarDataMedalhista(data) {
  if (!data) return "";
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}/${ano}`;
}

async function carregarUltimosMedalhistas() {
  const elCard = document.getElementById("home-ultimos-medalhistas");
  const elLista = document.getElementById("lista-ultimos-medalhistas");
  if (!elCard) return;
  try {
    const resp = await fetch("/api/home/medalhas-recentes");
    const medalhistas = await resp.json();
    if (!resp.ok || !medalhistas.length) return;

    elCard.style.display = "block";
    elLista.innerHTML = medalhistas.map(m => `
      <div class="cartao-alerta" style="padding:10px 14px;">
        <div>
          <a href="/atleta/${encodeURIComponent(m.nome_usuario)}" style="color: var(--azul); font-weight:600; text-decoration:none;">
            ${MEDALHA_EMOJI[m.medalha] || ""} ${m.nome}
          </a>
        </div>
        <div class="cartao-alerta-federacao">${m.campeonato || "Competição"}${m.data ? " · " + formatarDataMedalhista(m.data) : ""}</div>
      </div>
    `).join("");
  } catch (err) {
    // sem medalhistas recentes — quadro fica escondido
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

// Convites Mestre-Aluno pendentes esperando o usuário logado aceitar —
// em qualquer um dos dois papéis (a mesma pessoa pode ser Mestre de uns
// e Aluno de outros ao mesmo tempo). Ver api_vinculos_pendentes (app.py).
async function carregarVinculosPendentes() {
  const elBloco = document.getElementById("home-vinculos-pendentes");
  if (!elBloco) return;
  try {
    const resp = await fetch("/api/vinculos-pendentes");
    if (!resp.ok) return;
    const pendentes = await resp.json();
    if (!pendentes.length) {
      elBloco.style.display = "none";
      elBloco.innerHTML = "";
      return;
    }
    elBloco.style.display = "block";
    elBloco.innerHTML = pendentes.map((p, i) => `
      <div class="aviso-lembrete">
        <span>
          ${p.papel === "mestre"
            ? `<strong>${p.nome}</strong> pediu pra ser seu aluno.`
            : `<strong>${p.nome}</strong> te convidou como aluno(a).`}
        </span>
        <button type="button" class="btn-aceitar-vinculo-home" data-indice="${i}">Aceitar</button>
        <button type="button" class="btn-secundario btn-recusar-vinculo-home" data-indice="${i}">Recusar</button>
      </div>
    `).join("");
    elBloco.querySelectorAll(".btn-aceitar-vinculo-home").forEach(btn => {
      btn.addEventListener("click", () => responderVinculoHome(pendentes[Number(btn.dataset.indice)], true));
    });
    elBloco.querySelectorAll(".btn-recusar-vinculo-home").forEach(btn => {
      btn.addEventListener("click", () => responderVinculoHome(pendentes[Number(btn.dataset.indice)], false));
    });
  } catch (err) {
    elBloco.style.display = "none";
  }
}

async function responderVinculoHome(pendente, aceitar) {
  // "papel: mestre" = EU sou o Mestre nesse vínculo (aceito/recuso pelo
  // lado de Meus Alunos, que exige assinatura Mestre PRO — fetchAutenticado
  // já redireciona pra /assinatura num 402, mesmo tratamento usado no
  // resto do site); "papel: aluno" = EU sou o aluno (pelo lado de Meu
  // Mestre, só precisa estar logado) — mesma distinção usada em
  // meus-alunos.js/carreira.js.
  const url = pendente.papel === "mestre"
    ? `/api/meus-alunos/${pendente.aluno_id}${aceitar ? "/aceitar" : ""}`
    : `/api/carreira/meu-mestre/${pendente.mestre_id}${aceitar ? "/aceitar" : ""}`;
  try {
    await fetchAutenticado(url, { method: aceitar ? "POST" : "DELETE", headers: { "Content-Type": "application/json" } });
  } catch (err) {
    // fetchAutenticado já redirecionou (sessão expirada / assinatura
    // necessária) — não há mais nada a fazer aqui.
    return;
  }
  carregarVinculosPendentes();
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

  carregarVinculosPendentes();

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
carregarUltimosMedalhistas();
