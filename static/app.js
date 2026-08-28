const TODAS = "todas";

// Guarda a Promise (não o resultado ainda) — o carregamento inicial mais
// abaixo espera ela resolver antes de decidir se chama carregarFiltroPadrao
// (também exige assinatura): sem esperar, fetchAutenticado já redirecionava
// sozinho pra /assinatura antes da pessoa nem ver o aviso.
const promessaBloqueioPlanoFree = bloquearSePlanoFree("#conteudo-plano-pro");

const elFederacaoOpcoes = document.getElementById("federacao-opcoes");
const elEvento = document.getElementById("evento");
const elGenero = document.getElementById("genero");
const elDataNascimento = document.getElementById("data_nascimento");
const elCategoriaCalculada = document.getElementById("categoria-calculada");
const elPesoKg = document.getElementById("peso_kg");
const elPesoSemKimono = document.getElementById("peso_sem_kimono");
const elPesoCalculado = document.getElementById("peso-calculado");
const elStatus = document.getElementById("status");
const elResultados = document.getElementById("resultados");
const elForm = document.getElementById("form-busca");
const elBtnBuscar = document.getElementById("btn-buscar");
const elBarraCarregamento = document.getElementById("barra-carregamento");
const elBtnCriarAlerta = document.getElementById("btn-criar-alerta");
const elStatusAlerta = document.getElementById("status-alerta");
const elBtnSalvarFiltroPadrao = document.getElementById("btn-salvar-filtro-padrao");
const elStatusFiltroPadrao = document.getElementById("status-filtro-padrao");

const LABEL_FEDERACAO = { cbjj: "CBJJ", fjjrio: "FJJRio", cbjjd: "CBJJD", cbjjo: "CBJJO", cbjje: "CBJJE", fpjj: "FPJJ", cbjjc: "CBJJC", adcc: "ADCC", ajp: "AJP" };

// Federações Smoothcomp: categorizam pela idade exata no dia da competição
// (não por ano de nascimento), então a categoria/peso calculados têm um
// formato de exibição diferente — ver _linhaCategoriaSmoothcomp abaixo.
const FEDERACOES_SMOOTHCOMP = ["adcc", "ajp"];

async function carregarFederacoes() {
  const resp = await fetchAutenticado("/api/federacoes");
  const federacoes = await resp.json();
  construirOpcoesFederacao(elFederacaoOpcoes, federacoes, onFederacaoMudou);
}

// Monta os checkboxes de federação: nenhuma marcada por padrão, sem atalho
// "Todas as federações" de propósito (removido em 26/08/2026 — buscar em
// todas as federações e todas as competições de uma vez é a combinação mais
// pesada do site, ~58 competições de uma tacada só; tirar o atalho evita
// disparar isso sem querer). Quem quiser mesmo buscar em tudo ainda
// consegue, marcando cada federação uma por uma.
function construirOpcoesFederacao(container, federacoes, onChange) {
  container.innerHTML = federacoes.map(f => `<label><input type="checkbox" value="${f.id}"> ${f.label}</label>`).join("");
  container.addEventListener("change", onChange);
}

// Retorna um id único (string), uma lista de ids (seleção múltipla) ou null
// se nada estiver marcado — nesse caso não buscamos nada (em vez de
// silenciosamente cair pra "todas as federações", que confundia: se uma
// federação demorasse/falhasse pra um termo específico, parecia que só uma
// tinha sido pesquisada).
function federacaoSelecionada(container) {
  const selecionadas = Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
  if (!selecionadas.length) return null;
  return selecionadas.length === 1 ? selecionadas[0] : selecionadas;
}

function federacaoParaParametro(selecao) {
  return Array.isArray(selecao) ? selecao.join(",") : selecao;
}

async function carregarEventos(federacao) {
  if (federacao === null) {
    elEvento.innerHTML = '<option value="">Selecione uma federação</option>';
    elEvento.disabled = true;
    elBtnBuscar.disabled = true;
    return;
  }

  if (federacao === TODAS || Array.isArray(federacao)) {
    const texto = federacao === TODAS
      ? "Todas as competições, de todas as federações"
      : `Todas as competições, das ${federacao.length} federações selecionadas`;
    elEvento.innerHTML = `<option value="${TODAS}" selected>${texto}</option>`;
    elEvento.disabled = true;
    elBtnBuscar.disabled = false;
    return;
  }

  elEvento.disabled = true;
  elEvento.innerHTML = '<option value="">Carregando competições...</option>';
  elBtnBuscar.disabled = true;

  try {
    const resp = await fetchAutenticado(`/api/eventos?federacao=${encodeURIComponent(federacao)}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar eventos");

    if (!dados.length) {
      elEvento.innerHTML = '<option value="">Nenhuma competição encontrada</option>';
      return;
    }
    elEvento.innerHTML =
      `<option value="${TODAS}">Todas as competições desta federação</option>` +
      dados.map(e => `<option value="${e.id}">${e.nome}</option>`).join("");
    elEvento.disabled = false;
    elBtnBuscar.disabled = false;
  } catch (err) {
    elEvento.innerHTML = '<option value="">Erro ao carregar</option>';
    mostrarStatus(`Não foi possível carregar as competições: ${err.message}`, true);
  }
}

function _linhaCategoriaSmoothcomp(fid, info) {
  const label = LABEL_FEDERACAO[fid] || fid;
  if (!info.categoria_idade) {
    return `${label}: ${info.aviso_categoria || "sem categoria"}`;
  }
  let linha = `${label}: ${info.categoria_idade} (${info.idade_exata} anos em ${info.data_referencia})`;
  if (info.peso_categoria) linha += `, peso: ${info.peso_categoria}`;
  else if (info.aviso_peso) linha += ", selecione o gênero para calcular o peso";
  return linha;
}

async function atualizarCategoriaCalculada() {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  const dataNascimento = elDataNascimento.value;
  const peso = elPesoKg.value;
  const pesoSemKimono = elPesoSemKimono.value;
  const pesoPreenchido = peso || pesoSemKimono;
  const genero = elGenero.value;
  const evento = elEvento.value;

  if (!dataNascimento || federacao === null) {
    elCategoriaCalculada.textContent = "";
    elPesoCalculado.textContent = "";
    return;
  }

  const params = new URLSearchParams({ federacao: federacaoParaParametro(federacao), data_nascimento: dataNascimento });
  if (peso) params.set("peso_kg", peso);
  if (pesoSemKimono) params.set("peso_sem_kimono", pesoSemKimono);
  if (genero) params.set("genero", genero);
  if (evento) params.set("evento", evento);

  try {
    const resp = await fetchAutenticado(`/api/categoria?${params.toString()}`);
    const dados = await resp.json();
    if (!resp.ok) {
      elCategoriaCalculada.textContent = "";
      elPesoCalculado.textContent = "";
      return;
    }

    if (federacao === TODAS || Array.isArray(federacao)) {
      const linhasIdade = Object.entries(dados.categorias || {})
        .map(([fid, info]) => FEDERACOES_SMOOTHCOMP.includes(fid) ? _linhaCategoriaSmoothcomp(fid, info) : `${LABEL_FEDERACAO[fid] || fid}: ${info.categoria_idade || "sem categoria"}`);
      elCategoriaCalculada.textContent = linhasIdade.join(" · ");

      if (pesoPreenchido) {
        const linhasPeso = Object.entries(dados.categorias || {})
          .filter(([fid]) => !FEDERACOES_SMOOTHCOMP.includes(fid))
          .map(([fid, info]) => `${LABEL_FEDERACAO[fid] || fid}: ${info.peso_categoria || (info.aviso_peso ? "selecione o gênero" : "—")}`);
        elPesoCalculado.textContent = linhasPeso.join(" · ");
      } else {
        elPesoCalculado.textContent = "";
      }
    } else if (FEDERACOES_SMOOTHCOMP.includes(federacao)) {
      elCategoriaCalculada.textContent = _linhaCategoriaSmoothcomp(federacao, dados);
      elPesoCalculado.textContent = "";
    } else {
      elCategoriaCalculada.textContent = dados.categoria_idade
        ? `Categoria: ${dados.categoria_idade}`
        : "Nenhuma categoria encontrada para essa data";

      if (pesoPreenchido) {
        elPesoCalculado.textContent = dados.peso_categoria
          ? `Categoria de peso: ${dados.peso_categoria}`
          : (dados.aviso_peso ? "Selecione o gênero para calcular o peso" : "Nenhuma categoria de peso encontrada");
      } else {
        elPesoCalculado.textContent = "";
      }
    }
  } catch (err) {
    elCategoriaCalculada.textContent = "";
    elPesoCalculado.textContent = "";
  }
}

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = ehErro ? "erro" : "";
}

function renderizarResultados(atletas) {
  if (!atletas.length) {
    elResultados.innerHTML = "";
    return;
  }

  // A API já devolve os atletas agrupados por federação e, dentro de cada
  // uma, em ordem cronológica — aqui desenhamos um bloco por federação e,
  // dentro dele, uma subseção por competição (agrupando por nome de
  // evento com um Map, em vez de assumir que já vêm contíguos — quando
  // duas competições da mesma federação caem exatamente na mesma data,
  // a ordem entre elas na resposta não é garantida).
  const blocosFederacao = [];
  let blocoFedAtual = null;
  for (const a of atletas) {
    if (!blocoFedAtual || blocoFedAtual.federacao !== a.federacao) {
      blocoFedAtual = { federacao: a.federacao || "—", eventos: new Map() };
      blocosFederacao.push(blocoFedAtual);
    }
    const chaveEvento = a.evento || "—";
    if (!blocoFedAtual.eventos.has(chaveEvento)) {
      blocoFedAtual.eventos.set(chaveEvento, { evento: chaveEvento, data: a.data || "", itens: [] });
    }
    blocoFedAtual.eventos.get(chaveEvento).itens.push(a);
  }

  elResultados.innerHTML = blocosFederacao.map(blocoFed => {
    const totalFederacao = [...blocoFed.eventos.values()].reduce((soma, ev) => soma + ev.itens.length, 0);
    return `
    <section class="bloco-federacao">
      <h2><img src="/img/federacoes/${(blocoFed.federacao || "").toLowerCase()}.png" class="logo-federacao" alt="" loading="lazy">${blocoFed.federacao} <span class="contagem">(${totalFederacao})</span></h2>
      ${[...blocoFed.eventos.values()].map(bloco => {
        const temSituacao = bloco.itens.some(a => a.pagamento);
        const situacaoOk = new Set(["Pago", "Confirmado"]);
        return `
        <div class="bloco-competicao">
          <h3 class="destaque-competicao">
            ${bloco.evento} <span class="contagem">(${bloco.itens.length})</span>
            ${bloco.data ? `<span class="destaque-competicao-data">${bloco.data}</span>` : ""}
          </h3>
          <table>
            <thead>
              <tr>
                <th>Atleta</th>
                <th>Equipe</th>
                <th>Categoria</th>
                <th>Gênero</th>
                <th>Faixa</th>
                <th>Peso</th>
                ${temSituacao ? "<th>Situação</th>" : ""}
              </tr>
            </thead>
            <tbody>
              ${bloco.itens.map(a => `
                <tr>
                  <td>${a.nome || ""}</td>
                  <td>${a.equipe || ""}</td>
                  <td>${a.categoria_idade || ""}</td>
                  <td>${a.genero || ""}</td>
                  <td>${a.faixa || ""}</td>
                  <td>${a.peso || ""}</td>
                  ${temSituacao ? `<td class="${situacaoOk.has(a.pagamento) ? 'pago' : 'nao-pago'}">${a.pagamento || ""}</td>` : ""}
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `; }).join("")}
    </section>
  `; }).join("");
}

function onFederacaoMudou() {
  elResultados.innerHTML = "";
  mostrarStatus("");
  carregarEventos(federacaoSelecionada(elFederacaoOpcoes));
  atualizarCategoriaCalculada();
}

elGenero.addEventListener("change", atualizarCategoriaCalculada);
elDataNascimento.addEventListener("input", atualizarCategoriaCalculada);
elPesoKg.addEventListener("input", atualizarCategoriaCalculada);
elPesoSemKimono.addEventListener("input", atualizarCategoriaCalculada);
elEvento.addEventListener("change", atualizarCategoriaCalculada);

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  if (federacao === null) {
    mostrarStatus("Selecione ao menos uma federação para buscar.", true);
    return;
  }
  const evento = elEvento.value;
  if (!evento) return;

  const params = new URLSearchParams({
    federacao: federacaoParaParametro(federacao),
    evento,
    genero: elGenero.value,
    data_nascimento: elDataNascimento.value,
    faixa: document.getElementById("faixa").value,
    peso_kg: elPesoKg.value,
    peso_sem_kimono: elPesoSemKimono.value,
    nome: document.getElementById("nome").value,
    equipe: document.getElementById("equipe").value,
  });

  elBtnBuscar.disabled = true;
  const buscandoTudo = federacao === TODAS || Array.isArray(federacao) || evento === TODAS;
  mostrarStatus(buscandoTudo ? "Buscando em várias competições, pode levar alguns segundos..." : "Buscando...");
  elResultados.innerHTML = "";
  elBarraCarregamento.hidden = false;

  try {
    const resp = await fetchAutenticado(`/api/atletas?${params.toString()}`);
    let dados;
    try {
      dados = await resp.json();
    } catch {
      throw new Error("o servidor demorou demais pra responder (busca muito ampla). Tente selecionar menos federações ou uma competição específica.");
    }
    if (!resp.ok) throw new Error(dados.erro || "erro na busca");

    renderizarResultados(dados.atletas);
    let resumo = `${dados.total} atleta(s) encontrado(s)`;
    if (dados.eventos_pesquisados > 1) {
      resumo += ` em ${dados.eventos_pesquisados} competições`;
    }
    resumo += ".";
    const avisos = (dados.avisos || []).join(" ");
    mostrarStatus(avisos ? `${resumo} ${avisos}` : resumo);
  } catch (err) {
    mostrarStatus(`Erro na busca: ${err.message}`, true);
  } finally {
    elBtnBuscar.disabled = false;
    elBarraCarregamento.hidden = true;
  }
});

elBtnCriarAlerta.addEventListener("click", async () => {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  if (federacao === null) {
    elStatusAlerta.textContent = "Selecione ao menos uma federação antes de criar o alerta.";
    elStatusAlerta.className = "erro";
    return;
  }
  const titulo = prompt("Nome para esse alerta (ex: \"Roxa adulto masculino leve\"):");
  if (!titulo) return;

  const corpo = {
    titulo,
    federacao: federacaoParaParametro(federacao),
    genero: elGenero.value,
    data_nascimento: elDataNascimento.value,
    faixa: document.getElementById("faixa").value,
    peso_kg: elPesoKg.value,
    peso_sem_kimono: elPesoSemKimono.value,
    nome: document.getElementById("nome").value,
    equipe: document.getElementById("equipe").value,
  };

  elBtnCriarAlerta.disabled = true;
  elStatusAlerta.textContent = "Criando alerta...";
  elStatusAlerta.className = "";

  try {
    const resp = await fetchAutenticado("/api/alertas", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao criar alerta");
    elStatusAlerta.textContent = `Alerta "${titulo}" criado! Veja em "Meus Alertas".`;
  } catch (err) {
    elStatusAlerta.textContent = `Erro ao criar alerta: ${err.message}`;
    elStatusAlerta.className = "erro";
  } finally {
    elBtnCriarAlerta.disabled = false;
  }
});

function valoresFiltroAtual() {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  return {
    federacao: federacao === null ? "" : federacaoParaParametro(federacao),
    genero: elGenero.value,
    data_nascimento: elDataNascimento.value,
    faixa: document.getElementById("faixa").value,
    peso_kg: elPesoKg.value,
    peso_sem_kimono: elPesoSemKimono.value,
    nome: document.getElementById("nome").value,
    equipe: document.getElementById("equipe").value,
  };
}

// Aplica um filtro salvo aos campos do formulário — usado ao carregar a
// página, pra restaurar o filtro padrão do usuário (ver carregarFiltroPadrao).
function aplicarFiltroAosCampos(filtro) {
  if (!filtro) return;

  const checkboxes = Array.from(elFederacaoOpcoes.querySelectorAll('input[type="checkbox"]'));
  const todasCheckbox = checkboxes[0];
  const individuais = checkboxes.slice(1);
  if (filtro.federacao === TODAS || !filtro.federacao) {
    todasCheckbox.checked = true;
    individuais.forEach(c => { c.checked = false; });
  } else {
    const valores = filtro.federacao.split(",");
    individuais.forEach(c => { c.checked = valores.includes(c.value); });
    todasCheckbox.checked = !individuais.some(c => c.checked);
  }

  elGenero.value = filtro.genero || "";
  elDataNascimento.value = filtro.data_nascimento || "";
  document.getElementById("faixa").value = filtro.faixa || "";
  elPesoKg.value = filtro.peso_kg || "";
  elPesoSemKimono.value = filtro.peso_sem_kimono || "";
  document.getElementById("nome").value = filtro.nome || "";
  document.getElementById("equipe").value = filtro.equipe || "";
}

function mostrarLinkRemoverFiltroPadrao() {
  elStatusFiltroPadrao.innerHTML = 'Filtro padrão aplicado. <a href="#" id="link-remover-filtro-padrao">Remover filtro padrão</a>';
  document.getElementById("link-remover-filtro-padrao").addEventListener("click", async (ev) => {
    ev.preventDefault();
    try {
      await fetchAutenticado("/api/buscador/filtro-padrao", { method: "DELETE" });
      elStatusFiltroPadrao.textContent = "Filtro padrão removido.";
    } catch (err) {
      // fetchAutenticado já trata sessão/assinatura; outros erros ficam silenciosos aqui
    }
  });
}

async function carregarFiltroPadrao() {
  try {
    const resp = await fetchAutenticado("/api/buscador/filtro-padrao");
    const dados = await resp.json();
    if (dados.filtro) {
      aplicarFiltroAosCampos(dados.filtro);
      mostrarLinkRemoverFiltroPadrao();
    }
  } catch (err) {
    // sem filtro padrão salvo, ou erro ao buscar — segue com o formulário vazio
  }
}

elBtnSalvarFiltroPadrao.addEventListener("click", async () => {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  if (federacao === null) {
    elStatusFiltroPadrao.textContent = "Selecione ao menos uma federação antes de salvar.";
    elStatusFiltroPadrao.className = "erro";
    return;
  }

  elBtnSalvarFiltroPadrao.disabled = true;
  elStatusFiltroPadrao.className = "";
  elStatusFiltroPadrao.textContent = "Salvando filtro padrão...";

  try {
    await fetchAutenticado("/api/buscador/filtro-padrao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(valoresFiltroAtual()),
    });
    mostrarLinkRemoverFiltroPadrao();
  } catch (err) {
    elStatusFiltroPadrao.textContent = `Erro ao salvar filtro padrão: ${err.message}`;
    elStatusFiltroPadrao.className = "erro";
  } finally {
    elBtnSalvarFiltroPadrao.disabled = false;
  }
});

carregarFederacoes()
  .then(() => promessaBloqueioPlanoFree)
  .then((bloqueado) => bloqueado ? null : carregarFiltroPadrao())
  .then(() => {
    elResultados.innerHTML = "";
    mostrarStatus("");
    atualizarCategoriaCalculada();
    return carregarEventos(federacaoSelecionada(elFederacaoOpcoes));
  })
  .then(() => {
    if (new URLSearchParams(window.location.search).get("auto") === "1") {
      elForm.requestSubmit();
    }
  });
