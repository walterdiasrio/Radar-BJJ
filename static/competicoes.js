const TODAS = "todas";

const elFederacaoOpcoes = document.getElementById("federacao-opcoes");
const elPublicoAdulto = document.getElementById("publico-adulto");
const elPublicoKids = document.getElementById("publico-kids");
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

// Monta os checkboxes de federação: "Todas" marcada por padrão; marcar uma
// individual desmarca "Todas"; desmarcar a última individual volta para "Todas".
function construirOpcoesFederacao(container, federacoes, onChange) {
  container.innerHTML =
    `<label class="opcao-todas"><input type="checkbox" value="${TODAS}" checked> Todas as federações</label>` +
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

// Retorna TODAS, um id único (string) ou uma lista de ids (seleção múltipla).
function federacaoSelecionada(container) {
  const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"]'));
  if (checkboxes[0].checked) return TODAS;
  const selecionadas = checkboxes.slice(1).filter(c => c.checked).map(c => c.value);
  if (!selecionadas.length) return TODAS;
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

// "ambos" (competições que misturam categorias kids e adulto no mesmo
// evento, ex: "Pré Mirim a Master") aparece nos dois filtros.
function competicoesFiltradas() {
  const mostrarAdulto = elPublicoAdulto.checked;
  const mostrarKids = elPublicoKids.checked;
  return competicoesCarregadas.filter(c => {
    if (c.publico === "ambos") return mostrarAdulto || mostrarKids;
    if (c.publico === "kids") return mostrarKids;
    return mostrarAdulto;
  });
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
          </tr>
        `).join("")}
      </tbody>
    </table>
    </section>
  `).join("");
}

async function carregar() {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  elBtn.disabled = true;
  elPublicoAdulto.disabled = true;
  elPublicoKids.disabled = true;
  mostrarStatus("Carregando competições, pode levar alguns segundos...");
  elResultados.innerHTML = "";

  try {
    const resp = await fetchAutenticado(`/api/competicoes?federacao=${encodeURIComponent(federacaoParaParametro(federacao))}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar competições");

    competicoesCarregadas = dados.competicoes;
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
  }
}

elForm.addEventListener("submit", (ev) => {
  ev.preventDefault();
  carregar();
});

elPublicoAdulto.addEventListener("change", aplicarFiltroPublico);
elPublicoKids.addEventListener("change", aplicarFiltroPublico);

carregarFederacoes().then(carregar);
