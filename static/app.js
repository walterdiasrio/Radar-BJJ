const TODAS = "todas";

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
const elBtnCriarAlerta = document.getElementById("btn-criar-alerta");
const elStatusAlerta = document.getElementById("status-alerta");

const LABEL_FEDERACAO = { cbjj: "CBJJ", fjjrio: "FJJRio", cbjjd: "CBJJD", cbjjo: "CBJJO", cbjje: "CBJJE", fpjj: "FPJJ", adcc: "ADCC" };

async function carregarFederacoes() {
  const resp = await fetchAutenticado("/api/federacoes");
  const federacoes = await resp.json();
  construirOpcoesFederacao(elFederacaoOpcoes, federacoes, onFederacaoMudou);
}

// Monta os checkboxes de federação: "Todas" marcada por padrão; marcar uma
// individual desmarca "Todas"; desmarcar a última individual volta pra "Todas".
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

async function carregarEventos(federacao) {
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

function _linhaCategoriaAdcc(info) {
  if (!info.categoria_idade) {
    return `ADCC: ${info.aviso_categoria || "sem categoria"}`;
  }
  let linha = `ADCC: ${info.categoria_idade} (${info.idade_exata} anos em ${info.data_referencia})`;
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

  if (!dataNascimento) {
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

    if (typeof federacao !== "string") {
      const linhasIdade = Object.entries(dados.categorias || {})
        .map(([fid, info]) => fid === "adcc" ? _linhaCategoriaAdcc(info) : `${LABEL_FEDERACAO[fid] || fid}: ${info.categoria_idade || "sem categoria"}`);
      elCategoriaCalculada.textContent = linhasIdade.join(" · ");

      if (pesoPreenchido) {
        const linhasPeso = Object.entries(dados.categorias || {})
          .filter(([fid]) => fid !== "adcc")
          .map(([fid, info]) => `${LABEL_FEDERACAO[fid] || fid}: ${info.peso_categoria || (info.aviso_peso ? "selecione o gênero" : "—")}`);
        elPesoCalculado.textContent = linhasPeso.join(" · ");
      } else {
        elPesoCalculado.textContent = "";
      }
    } else if (federacao === "adcc") {
      elCategoriaCalculada.textContent = _linhaCategoriaAdcc(dados);
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
  // uma, em ordem cronológica de competição — aqui só precisamos desenhar
  // um bloco por federação, na sequência em que eles chegam.
  const blocos = [];
  let blocoAtual = null;
  for (const a of atletas) {
    if (!blocoAtual || blocoAtual.federacao !== a.federacao) {
      blocoAtual = { federacao: a.federacao || "—", itens: [] };
      blocos.push(blocoAtual);
    }
    blocoAtual.itens.push(a);
  }

  elResultados.innerHTML = blocos.map(bloco => {
    const temSituacao = bloco.itens.some(a => a.pagamento);
    const situacaoOk = new Set(["Pago", "Confirmado"]);
    return `
    <section class="bloco-federacao">
      <h2>${bloco.federacao} <span class="contagem">(${bloco.itens.length})</span></h2>
      <table>
        <thead>
          <tr>
            <th>Atleta</th>
            <th>Equipe</th>
            <th>Competição</th>
            <th>Data</th>
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
              <td>${a.evento || ""}</td>
              <td>${a.data || ""}</td>
              <td>${a.categoria_idade || ""}</td>
              <td>${a.genero || ""}</td>
              <td>${a.faixa || ""}</td>
              <td>${a.peso || ""}</td>
              ${temSituacao ? `<td class="${situacaoOk.has(a.pagamento) ? 'pago' : 'nao-pago'}">${a.pagamento || ""}</td>` : ""}
            </tr>
          `).join("")}
        </tbody>
      </table>
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

  try {
    const resp = await fetchAutenticado(`/api/atletas?${params.toString()}`);
    const dados = await resp.json();
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
  }
});

elBtnCriarAlerta.addEventListener("click", async () => {
  const federacao = federacaoSelecionada(elFederacaoOpcoes);
  const titulo = prompt("Nome pra esse alerta (ex: \"Roxa adulto masculino leve\"):");
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

carregarFederacoes().then(() => carregarEventos(TODAS));
