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

// O Vinícius (dono da conta de demonstração do site) não conta como "gente
// suficiente" sozinho pra tirar o quadro fictício do ar — sem isso, o
// quadro passava a mostrar só ele repetido várias vezes assim que ele
// lançava a primeira medalha, o que não passa a impressão de comunidade
// que o quadro fictício tenta dar enquanto isso. Ver carregarUltimosMedalhistas.
const NOME_USUARIO_IGNORADO_NA_CONTAGEM_REAL = "vinibulba";

// Quadro fixo, sem nenhum atleta/conta real por trás — só pra não deixar o
// quadro "Últimos Medalhistas" vazio na home antes de existir gente
// suficiente cadastrando resultado de verdade. Assim que a API devolver
// pelo menos 1 medalhista real ALÉM do Vinícius, isso para de ser usado
// sozinho (ver carregarUltimosMedalhistas) — remover esta lista (e a
// constante acima) quando não precisar mais.
const MEDALHISTAS_FICTICIOS = [
  { nome: "Rafael Monteiro Duarte", medalha: "ouro", campeonato: "Saquarema Winter", data: "2026-08-20" },
  { nome: "Camila Ferraz Nogueira", medalha: "prata", campeonato: "Saquarema Winter", data: "2026-08-16" },
  { nome: "Bruno Cavalcanti Lima", medalha: "ouro", campeonato: "Saquarema Winter", data: "2026-08-10" },
  { nome: "Juliana Prado Azevedo", medalha: "bronze", campeonato: "Saquarema Winter", data: "2026-08-02" },
];

function itemMedalhista(m, comLink) {
  const nomeHtml = `${MEDALHA_EMOJI[m.medalha] || ""} ${m.nome}`;
  const nomeEl = comLink
    ? `<a href="/atleta/${encodeURIComponent(m.nome_usuario)}" style="color: var(--azul); font-weight:600; text-decoration:none;">${nomeHtml}</a>`
    : `<span style="color: var(--azul); font-weight:600;">${nomeHtml}</span>`;
  return `
    <div class="cartao-alerta" style="padding:10px 14px;">
      <div>${nomeEl}</div>
      <div class="cartao-alerta-federacao">${m.campeonato || "Competição"}${m.data ? " · " + formatarDataMedalhista(m.data) : ""}</div>
    </div>
  `;
}

async function carregarUltimosMedalhistas() {
  const elCard = document.getElementById("home-ultimos-medalhistas");
  const elLista = document.getElementById("lista-ultimos-medalhistas");
  if (!elCard) return;
  try {
    const resp = await fetch("/api/home/medalhas-recentes");
    const medalhistas = await resp.json();
    if (!resp.ok) return;

    elCard.style.display = "block";
    const temOutraPessoaReal = medalhistas.some(m => m.nome_usuario !== NOME_USUARIO_IGNORADO_NA_CONTAGEM_REAL);
    if (temOutraPessoaReal) {
      elLista.innerHTML = medalhistas.map(m => itemMedalhista(m, true)).join("");
    } else {
      const reaisDoVinicius = medalhistas.map(m => itemMedalhista(m, true));
      const fakesParaCompletar = MEDALHISTAS_FICTICIOS.slice(0, Math.max(0, 5 - reaisDoVinicius.length)).map(m => itemMedalhista(m, false));
      elLista.innerHTML = reaisDoVinicius.concat(fakesParaCompletar).join("");
    }
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

function formatarDataAulaHome(data) {
  const [ano, mes, dia] = data.split("-");
  return `${dia}/${mes}`;
}

function renderizarConteudoTurmaAulas(turma) {
  if (turma.aulas.length) {
    return turma.aulas.map(aula => `
      <div class="cartao-alerta" style="padding:10px 14px;">
        <div class="cartao-alerta-federacao">${formatarDataAulaHome(aula.data)}</div>
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:6px;">
          ${aula.posicoes.map(pos => `<span style="background:#eef2f6; border-radius:20px; padding:3px 10px; font-size:0.8rem; font-weight:700;">${pos}</span>`).join("")}
        </div>
      </div>
    `).join("");
  }

  if (turma.datas_sugeridas.length) {
    return `
      <p style="color:#55606b; font-size:0.85rem; margin-top:0;">Nenhuma aula registrada ainda pra essa turma. Próximas datas de treino:</p>
      ${turma.datas_sugeridas.map(data => `
        <div class="cartao-alerta" style="padding:10px 14px; display:flex; justify-content:space-between; align-items:center;">
          <span>${formatarDataAulaHome(data)}</span>
          <a href="/turmas?turma=${turma.id}&aba=futuras"><button type="button" class="btn-secundario">Criar Aula</button></a>
        </div>
      `).join("")}
    `;
  }

  return `
    <p style="color:#55606b; font-size:0.85rem; margin-top:0;">Essa turma ainda não tem dias da semana cadastrados.</p>
    <a href="/turmas?turma=${turma.id}"><button type="button" class="btn-secundario">Editar turma</button></a>
  `;
}

function renderizarProximasAulasHome(turmasComAulas) {
  const elCard = document.getElementById("home-proximas-aulas-turmas");
  const elSeletor = document.getElementById("home-aulas-seletor-turmas");
  const elConteudo = document.getElementById("home-aulas-conteudo-turma");
  if (!elCard) return;

  elCard.style.display = "block";

  if (!turmasComAulas.length) {
    elSeletor.style.display = "none";
    elConteudo.innerHTML = `
      <p style="color:#55606b; font-size:0.85rem; margin-top:0;">Você ainda não tem nenhuma turma cadastrada.</p>
      <a href="/turmas?nova=1"><button type="button" class="btn-secundario">Criar turma e lançar aulas</button></a>
    `;
    return;
  }

  const mostrarConteudo = (turmaId) => {
    const turma = turmasComAulas.find(t => t.id === turmaId);
    elConteudo.innerHTML = renderizarConteudoTurmaAulas(turma);
    elSeletor.querySelectorAll(".tab-carreira-btn").forEach(btn => {
      btn.classList.toggle("ativo", Number(btn.dataset.id) === turmaId);
    });
  };

  if (turmasComAulas.length > 1) {
    elSeletor.style.display = "flex";
    elSeletor.innerHTML = turmasComAulas.map(t => `
      <button type="button" class="tab-carreira-btn" data-id="${t.id}">${t.nome ? t.nome + " — " : ""}${t.categoria}</button>
    `).join("");
    elSeletor.querySelectorAll(".tab-carreira-btn").forEach(btn => {
      btn.addEventListener("click", () => mostrarConteudo(Number(btn.dataset.id)));
    });
  } else {
    elSeletor.style.display = "none";
  }

  mostrarConteudo(turmasComAulas[0].id);
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

  if (resumo.proximas_aulas_turmas) {
    renderizarProximasAulasHome(resumo.proximas_aulas_turmas);
  }

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
