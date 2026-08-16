const TODAS = "todas";

const elFederacaoOpcoes = document.getElementById("federacao-opcoes");
const elPublicoAdulto = document.getElementById("publico-adulto");
const elPublicoKids = document.getElementById("publico-kids");
const elEstadoOpcoes = document.getElementById("estado-opcoes");
const elForm = document.getElementById("form-filtro");
const elBtn = document.getElementById("btn-carregar");
const elStatus = document.getElementById("status");
const elResultados = document.getElementById("resultados");

let competicoesCarregadas = [];

async function carregarFederacoes() {
  const resp = await fetchAutenticado("/api/federacoes");
  const federacoes = await resp.json();
  construirOpcoesFederacao(elFederacaoOpcoes, federacoes, carregar);
}

// Monta os checkboxes de federação: nenhuma marcada por padrão; marcar uma
// individual desmarca "Todas"; desmarcar a última individual volta para "Todas"
// (mas a busca sem nada marcado já considera todas as federações, ver
// federacaoSelecionada).
function construirOpcoesFederacao(container, federacoes, onChange) {
  container.innerHTML =
    `<label class="opcao-todas"><input type="checkbox" value="${TODAS}"> Todas as federações</label>` +
    federacoes.map(f => `<label><input type="checkbox" value="${f.id}"> ${f.label}</label>`).join("");

  const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"]'));
  const todasCheckbox = checkboxes[0];
  const individuais = checkboxes.slice(1);

  container.addEventListener("change", (ev) => {
    if (ev.target === todasCheckbox) {
      if (todasCheckbox.checked) individuais.forEach(c => { c.checked = false; });
    } else {
      if (ev.target.checked) todasCheckbox.checked = false;
      if (!individuais.some(c => c.checked)) todasCheckbox.checked = true;
    }
    onChange();
  });
}

// Retorna TODAS, um id único (string), uma lista de ids (seleção múltipla)
// ou null se nada estiver marcado — nesse caso não buscamos nada (em vez de
// cair pra "todas as federações" sem o usuário ter pedido isso).
function federacaoSelecionada(container) {
  const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"]'));
  if (checkboxes[0].checked) return TODAS;
  const selecionadas = checkboxes.slice(1).filter(c => c.checked).map(c => c.value);
  if (!selecionadas.length) return null;
  return selecionadas.length === 1 ? selecionadas[0] : selecionadas;
}

function federacaoParaParametro(selecao) {
  return Array.isArray(selecao) ? selecao.join(",") : selecao;
}

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

function badgeInscricao(aberta) {
  if (aberta === true) return '<span class="badge-inscricao badge-aberta">Abertas</span>';
  if (aberta === false) return '<span class="badge-inscricao badge-fechada">Fechadas</span>';
  return '<span class="badge-inscricao badge-desconhecida">Não informado</span>';
}

function escapeAtributo(texto) {
  return (texto || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

function botoesAgenda(c) {
  const status = c.agenda_status || null;
  return `
    <div class="botoes-agenda"
      data-federacao="${escapeAtributo(c.federacao)}" data-nome="${escapeAtributo(c.nome)}"
      data-data="${escapeAtributo(c.data)}" data-local="${escapeAtributo(c.local)}">
      <button type="button" class="btn-agenda btn-agenda-interesse ${status === "interesse" ? "ativo" : ""}"
        data-status="interesse">Tenho Interesse</button>
      <button type="button" class="btn-agenda btn-agenda-inscrito ${status === "inscrito" ? "ativo" : ""}"
        data-status="inscrito">Inscrito</button>
    </div>
  `;
}

// "ambos" (competições que misturam categorias kids e adulto no mesmo
// evento, ex: "Pré Mirim a Master") aparece nos dois filtros.
function competicoesFiltradas() {
  const mostrarAdulto = elPublicoAdulto.checked;
  const mostrarKids = elPublicoKids.checked;
  const estado = elEstadoOpcoes.value;
  return competicoesCarregadas.filter(c => {
    if (estado && c.uf !== estado) return false;
    if (c.publico === "ambos") return mostrarAdulto || mostrarKids;
    if (c.publico === "kids") return mostrarKids;
    return mostrarAdulto;
  });
}

// Monta a lista de estados só com as UFs que de fato apareceram nos
// resultados carregados — evita mostrar opções vazias. Mantém a seleção
// atual se ainda fizer sentido depois de recarregar.
const NOMES_UF = {
  AC: "Acre", AL: "Alagoas", AP: "Amapá", AM: "Amazonas", BA: "Bahia",
  CE: "Ceará", DF: "Distrito Federal", ES: "Espírito Santo", GO: "Goiás",
  MA: "Maranhão", MT: "Mato Grosso", MS: "Mato Grosso do Sul", MG: "Minas Gerais",
  PA: "Pará", PB: "Paraíba", PR: "Paraná", PE: "Pernambuco", PI: "Piauí",
  RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RS: "Rio Grande do Sul",
  RO: "Rondônia", RR: "Roraima", SC: "Santa Catarina", SP: "São Paulo",
  SE: "Sergipe", TO: "Tocantins",
};

function popularEstados() {
  const selecionadoAntes = elEstadoOpcoes.value;
  const ufs = [...new Set(competicoesCarregadas.map(c => c.uf).filter(Boolean))].sort();
  elEstadoOpcoes.innerHTML =
    '<option value="">Todos os estados</option>' +
    ufs.map(uf => `<option value="${uf}">${NOMES_UF[uf] || uf} (${uf})</option>`).join("");
  if (ufs.includes(selecionadoAntes)) elEstadoOpcoes.value = selecionadoAntes;
}

function aplicarFiltroPublico() {
  const filtradas = competicoesFiltradas();
  renderizarCompeticoes(filtradas);
  const resumo = `${filtradas.length} de ${competicoesCarregadas.length} competição(ões) encontrada(s).`;
  mostrarStatus(resumo);
}

function renderizarCompeticoes(competicoes) {
  if (!competicoes.length) {
    elResultados.innerHTML = "";
    return;
  }

  // A API já devolve tudo em ordem cronológica; aqui só agrupamos por mês.
  const blocosMes = [];
  let blocoAtual = null;
  for (const c of competicoes) {
    if (!blocoAtual || blocoAtual.mes !== c.mes) {
      blocoAtual = { mes: c.mes, itens: [] };
      blocosMes.push(blocoAtual);
    }
    blocoAtual.itens.push(c);
  }

  elResultados.innerHTML = blocosMes.map(bloco => `
    <section class="secao-mes">
    <div class="bloco-mes">${bloco.mes} <span class="contagem">(${bloco.itens.length})</span></div>
    <table>
      <thead>
        <tr>
          <th>Federação</th>
          <th>Competição</th>
          <th>Data</th>
          <th>Local</th>
          <th>Inscrições</th>
          <th>Minha Agenda</th>
        </tr>
      </thead>
      <tbody>
        ${bloco.itens.map(c => `
          <tr>
            <td>${c.federacao || ""}</td>
            <td>${c.nome || ""}</td>
            <td>${c.data || ""}</td>
            <td>${c.local || ""}</td>
            <td>${badgeInscricao(c.inscricoes_abertas)}</td>
            <td>${botoesAgenda(c)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
    </section>
  `).join("");

  elResultados.querySelectorAll(".btn-agenda").forEach(btn => {
    btn.addEventListener("click", () => alternarAgenda(btn));
  });
}

async function alternarAgenda(btn) {
  const container = btn.closest(".botoes-agenda");
  const { federacao, nome, data, local } = container.dataset;
  const jaAtivo = btn.classList.contains("ativo");
  const status = btn.dataset.status;

  container.querySelectorAll(".btn-agenda").forEach(b => b.disabled = true);

  try {
    if (jaAtivo) {
      const resp = await fetchAutenticado("/api/agenda", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ federacao, nome, data }),
      });
      if (!resp.ok) throw new Error("não consegui desmarcar");
      container.querySelectorAll(".btn-agenda").forEach(b => b.classList.remove("ativo"));
    } else {
      const resp = await fetchAutenticado("/api/agenda", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ federacao, nome, data, local, status }),
      });
      const dados = await resp.json();
      if (!resp.ok) throw new Error(dados.erro || "não consegui marcar");
      container.querySelectorAll(".btn-agenda").forEach(b => b.classList.remove("ativo"));
      btn.classList.add("ativo");
    }
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  } finally {
    container.querySelectorAll(".btn-agenda").forEach(b => b.disabled = false);
  }
}

async function carregar() {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  if (federacao === null) {
    competicoesCarregadas = [];
    elResultados.innerHTML = "";
    mostrarStatus("Selecione ao menos uma federação para buscar.", true);
    return;
  }
  elBtn.disabled = true;
  elPublicoAdulto.disabled = true;
  elPublicoKids.disabled = true;
  elEstadoOpcoes.disabled = true;
  mostrarStatus("Carregando competições, pode levar alguns segundos...");
  elResultados.innerHTML = "";

  try {
    const resp = await fetchAutenticado(`/api/competicoes?federacao=${encodeURIComponent(federacaoParaParametro(federacao))}`);
    let dados;
    try {
      dados = await resp.json();
    } catch {
      throw new Error("o servidor demorou demais pra responder (busca muito ampla). Tente selecionar menos federações.");
    }
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar competições");

    competicoesCarregadas = dados.competicoes;
    popularEstados();
    const filtradas = competicoesFiltradas();
    renderizarCompeticoes(filtradas);
    let resumo = `${filtradas.length} de ${dados.total} competição(ões) encontrada(s).`;
    const avisos = (dados.avisos || []).join(" ");
    mostrarStatus(avisos ? `${resumo} ${avisos}` : resumo);
  } catch (err) {
    mostrarStatus(`Erro ao carregar: ${err.message}`, true);
  } finally {
    elBtn.disabled = false;
    elPublicoAdulto.disabled = false;
    elPublicoKids.disabled = false;
    elEstadoOpcoes.disabled = false;
  }
}

elForm.addEventListener("submit", (ev) => {
  ev.preventDefault();
  carregar();
});

const elBtnCriarAlertaCompeticao = document.getElementById("btn-criar-alerta-competicao");
const elStatusAlertaCompeticao = document.getElementById("status-alerta-competicao");

elBtnCriarAlertaCompeticao.addEventListener("click", async () => {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  if (federacao === null) {
    elStatusAlertaCompeticao.textContent = "Selecione ao menos uma federação antes de criar o alerta.";
    elStatusAlertaCompeticao.className = "erro";
    return;
  }
  let publico = "todos";
  if (elPublicoAdulto.checked && !elPublicoKids.checked) publico = "adulto";
  else if (elPublicoKids.checked && !elPublicoAdulto.checked) publico = "kids";
  else if (!elPublicoAdulto.checked && !elPublicoKids.checked) {
    elStatusAlertaCompeticao.textContent = "Selecione ao menos um público (Adulto ou Kids) antes de criar o alerta.";
    elStatusAlertaCompeticao.className = "erro";
    return;
  }

  const titulo = prompt('Nome para esse alerta (ex: "Competições CBJJ Kids"):');
  if (!titulo) return;

  elBtnCriarAlertaCompeticao.disabled = true;
  elStatusAlertaCompeticao.textContent = "Criando alerta...";
  elStatusAlertaCompeticao.className = "";

  try {
    const resp = await fetchAutenticado("/api/alertas-competicao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo, federacao: federacaoParaParametro(federacao), publico }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao criar alerta");
    elStatusAlertaCompeticao.textContent = `Alerta "${titulo}" criado! Veja em "Meus Alertas".`;
  } catch (err) {
    elStatusAlertaCompeticao.textContent = `Erro ao criar alerta: ${err.message}`;
    elStatusAlertaCompeticao.className = "erro";
  } finally {
    elBtnCriarAlertaCompeticao.disabled = false;
  }
});

elPublicoAdulto.addEventListener("change", aplicarFiltroPublico);
elPublicoKids.addEventListener("change", aplicarFiltroPublico);
elEstadoOpcoes.addEventListener("change", aplicarFiltroPublico);

carregarFederacoes().then(carregar);
