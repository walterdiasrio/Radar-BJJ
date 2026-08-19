const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-turmas");
const elForm = document.getElementById("form-turma");
const elTurmaId = document.getElementById("turma_id");
const elNome = document.getElementById("turma_nome");
const elCategoria = document.getElementById("turma_categoria");
const elInicio = document.getElementById("turma_horario_inicio");
const elFim = document.getElementById("turma_horario_fim");
const elDiasSemana = document.getElementById("turma_dias_semana");
const elBtnSalvar = document.getElementById("btn-salvar-turma");
const elBtnCancelar = document.getElementById("btn-cancelar-edicao");
const elSecaoForm = document.getElementById("secao-form-turma");
const elSecaoLista = document.getElementById("secao-lista-turmas");
const elTituloForm = document.getElementById("titulo-form-turma");

// A página tem dois modos que não se misturam: "criar" (?nova=1 — só o
// formulário, chegou pelo submenu "Nova Turma") e "consultar" (?turma=<id>
// — só aquela turma específica, chegou pelo submenu com o nome dela). Sem
// parâmetro nenhum, mostra a lista completa (sem o formulário).
const parametrosUrl = new URLSearchParams(window.location.search);
const modoNovaTurma = parametrosUrl.get("nova") === "1";
const turmaIdFiltro = parametrosUrl.get("turma");

function aplicarModoPagina() {
  if (modoNovaTurma) {
    elSecaoForm.style.display = "";
    elSecaoLista.style.display = "none";
  } else {
    elSecaoForm.style.display = "none";
    elSecaoLista.style.display = "";
  }
}
aplicarModoPagina();

let meusAlunos = [];
let turmasAtuais = [];
let posicoesPorGrupo = {};
const planosExpandidos = new Set();
const pendentesExpandidos = new Set();
const historicoPorTurma = {}; // turmaId -> { mesAno: "YYYY-MM", aulas: [...] }
const pendentesPorTurma = {}; // turmaId -> [iso, ...] (dias de aula sem registro ainda)
const planoEditando = {}; // turmaId -> { id, data, posicoes } da aula em edição, ou undefined
const planoDataRapida = {}; // turmaId -> iso pré-preenchido ao clicar "Registrar aula" numa pendente
const planoIaExpandidos = new Set();
const planoIaEstado = {};
const plannerExpandidos = new Set();
const plannerEstado = {};
const NOMES_DIA_SEMANA = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarHorario(hhmm) {
  return (hhmm || "").slice(0, 5);
}

function formatarDataBr(iso) {
  if (!iso) return "";
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

const MESES_PT = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

function rotuloMesAno(iso) {
  if (!iso) return "Data não informada";
  const [ano, mes] = iso.split("-");
  return `${MESES_PT[Number(mes) - 1]} ${ano}`;
}

async function carregarMeusAlunos() {
  try {
    const resp = await fetchAutenticado("/api/meus-alunos");
    meusAlunos = resp.ok ? await resp.json() : [];
  } catch {
    meusAlunos = [];
  }
}

async function carregarPosicoes() {
  if (Object.keys(posicoesPorGrupo).length) return;
  try {
    const resp = await fetchAutenticado("/api/turmas/posicoes");
    posicoesPorGrupo = resp.ok ? await resp.json() : {};
  } catch {
    posicoesPorGrupo = {};
  }
}

function opcoesAlunosDisponiveis(turma) {
  const idsNaTurma = new Set(turma.alunos.map(a => a.usuario_id));
  return meusAlunos.filter(a => !idsNaTurma.has(a.usuario_id));
}

function mesAnoAtual() {
  return new Date().toISOString().slice(0, 7); // "YYYY-MM"
}

function renderizarPlanoAula(turma) {
  const expandido = planosExpandidos.has(turma.id);
  const historico = historicoPorTurma[turma.id] || { mesAno: mesAnoAtual(), aulas: [] };
  const edicao = planoEditando[turma.id];

  return `
    <div id="historico-turma-${turma.id}" style="margin-top:12px; border-top:1px solid var(--borda); padding-top:12px;">
      <button type="button" class="btn-secundario btn-plano-aula" data-id="${turma.id}">
        ${expandido ? "Esconder Histórico de Aulas" : "Histórico de Aulas"}
      </button>

      ${expandido ? `
        <div style="margin-top:12px;">
          <form class="form-plano-aula" data-turma-id="${turma.id}" data-editando-id="${edicao ? edicao.id : ""}">
            <div class="campo" style="max-width:220px;">
              <label>Data da aula</label>
              <input type="date" class="plano_data" required value="${edicao ? edicao.data : (planoDataRapida[turma.id] || "")}">
            </div>
            ${Object.entries(posicoesPorGrupo).map(([grupo, posicoes]) => `
              <div class="campo">
                <label>${grupo}</label>
                <div class="opcoes-federacao">
                  ${posicoes.map(p => `<label><input type="checkbox" value="${p}" ${edicao && edicao.posicoes.includes(p) ? "checked" : ""}> ${p}</label>`).join("")}
                </div>
              </div>
            `).join("")}
            <button type="submit">${edicao ? "Salvar edição" : "Salvar histórico"}</button>
            ${edicao ? `<button type="button" class="btn-secundario btn-cancelar-edicao-plano" data-turma-id="${turma.id}">Cancelar edição</button>` : ""}
          </form>

          <div class="campo" style="max-width:220px; margin-top:14px;">
            <label>Consultar mês</label>
            <input type="month" class="historico_mes_ano" data-turma-id="${turma.id}" value="${historico.mesAno}">
          </div>

          <div style="margin-top:14px;">
            <strong>Aulas dadas em ${rotuloMesAno(historico.mesAno)}${historico.aulas.length ? ` (${historico.aulas.length})` : ""}:</strong>
            ${historico.aulas.length ? "" : " nenhuma aula registrada nesse mês."}
            ${historico.aulas.map(p => `
              <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
                <div class="cartao-alerta-topo">
                  <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataBr(p.data)}</div>
                  <div style="display:flex; gap:8px;">
                    <button type="button" class="btn-secundario btn-editar-plano" data-turma-id="${turma.id}" data-plano-id="${p.id}">Editar</button>
                    <button type="button" class="btn-remover btn-remover-plano" data-turma-id="${turma.id}" data-plano-id="${p.id}">Remover</button>
                  </div>
                </div>
                <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
                  ${p.posicoes.map(pos => `<span style="background:#eef2f6; border-radius:20px; padding:3px 10px; font-size:0.8rem;">${pos}</span>`).join("")}
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}
    </div>
  `;
}

function renderizarAulasFuturas(turma) {
  const expandido = pendentesExpandidos.has(turma.id);
  const pendentes = pendentesPorTurma[turma.id] || [];

  return `
    <div style="margin-top:12px; border-top:1px solid var(--borda); padding-top:12px;">
      <button type="button" class="btn-secundario btn-aulas-futuras" data-id="${turma.id}">
        ${expandido ? "Esconder Aulas Futuras" : "Aulas Futuras"}
      </button>

      ${expandido ? `
        <div style="margin-top:12px;">
          <strong>Próximas aulas (ainda não registradas)${pendentes.length ? ` (${pendentes.length})` : ""}:</strong>
          ${pendentes.length ? "" : " nenhuma — todos os dias de aula do mês atual e do seguinte já têm registro, ou a turma não tem dias da semana cadastrados."}
          ${pendentes.map(iso => `
            <div class="cartao-alerta" style="margin-top:8px; padding:10px 14px; display:flex; align-items:center; justify-content:space-between; gap:10px;">
              <span>${formatarDataDiaSemana(iso)}</span>
              <button type="button" class="btn-secundario btn-registrar-pendente" data-turma-id="${turma.id}" data-data="${iso}">Registrar aula</button>
            </div>
          `).join("")}
        </div>
      ` : ""}
    </div>
  `;
}

function renderizarPlanoIA(turma) {
  const expandido = planoIaExpandidos.has(turma.id);
  const estado = planoIaEstado[turma.id] || {};
  const grupos = Object.keys(posicoesPorGrupo);

  return `
    <div style="margin-top:12px;">
      <button type="button" class="btn-secundario btn-plano-ia" data-id="${turma.id}">
        ${expandido ? "Esconder Plano de Aula IA" : "Plano de Aula IA"}
      </button>

      ${expandido ? `
        <div style="margin-top:12px;">
          <p style="color:#7c8894; font-size:0.85rem; margin-top:0;">
            A Inteligência Artificial analisa o histórico de aulas de sua turma, e com base nos objetivos
            traçados e no foco desejado, planeja as próximas aulas.
          </p>
          <div class="campo" style="max-width:420px;">
            <label>Foco (opcional)</label>
            <select class="plano_ia_foco" data-turma-id="${turma.id}">
              <option value="">Sem foco específico</option>
              ${grupos.map(g => `<option value="${g}" ${estado.foco === g ? "selected" : ""}>${g}</option>`).join("")}
            </select>
          </div>
          <div class="campo" style="max-width:420px;">
            <label>O que você quer nesse plano? (opcional, máx. 200 caracteres)</label>
            <textarea class="plano_ia_resumo" data-turma-id="${turma.id}" rows="3"
              placeholder="ex: turma está fraca na defesa, quero reforçar escapes e fundamentos essa semana"
              maxlength="200">${estado.resumo || ""}</textarea>
          </div>
          <button type="button" class="btn-gerar-plano-ia" data-id="${turma.id}" ${estado.carregando ? "disabled" : ""}>
            ${estado.carregando ? "Gerando..." : "Gerar sugestão com IA"}
          </button>
          <div style="color:#7c8894; font-size:0.78rem; margin-top:4px;">Limite: 2 gerações com IA por dia, por turma.</div>

          ${estado.erro ? `<div class="status-importacao erro" style="margin-top:8px;">${estado.erro}</div>` : ""}

          ${estado.resultado ? `
            <div style="margin-top:14px;">
              ${estado.resultado.ia === false ? `
                <div class="status-importacao" style="margin-bottom:8px;">
                  ${estado.resultado.aviso || "IA indisponível no momento — mostrando sugestão automática (sem IA)."}
                </div>
              ` : ""}
              ${estado.resultado.aulas.map((a, i) => `
                <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
                  <div class="cartao-alerta-topo">
                    <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataBr(a.data)}</div>
                    ${a.salvo
                      ? `<span style="color:#1a7d3a; font-size:0.85rem; font-weight:600;">Salvo ✓</span>`
                      : `<button type="button" class="btn-salvar-sugestao-ia" data-turma-id="${turma.id}" data-indice="${i}">Salvar no histórico</button>`}
                  </div>
                  <div style="display:flex; flex-wrap:wrap; gap:6px; margin-top:8px;">
                    ${a.posicoes.map(p => `<span style="background:#eef2f6; border-radius:20px; padding:3px 10px; font-size:0.8rem;">${p}</span>`).join("")}
                  </div>
                  ${a.observacao ? `<div style="color:#7c8894; font-size:0.82rem; margin-top:6px;">${a.observacao}</div>` : ""}
                </div>
              `).join("")}
              ${estado.resultado.aulas.some(a => !a.salvo) ? `
                <button type="button" class="btn-salvar-tudo-ia" data-id="${turma.id}" style="margin-top:10px;">Salvar plano inteiro no histórico</button>
              ` : ""}

              <div style="margin-top:16px; border-top:1px solid var(--borda); padding-top:12px;">
                ${renderizarPlanner(turma)}
              </div>
            </div>
          ` : ""}
        </div>
      ` : ""}
    </div>
  `;
}

function proximoMesAno() {
  const d = new Date();
  d.setMonth(d.getMonth() + 1);
  return d.toISOString().slice(0, 7); // "YYYY-MM"
}

function rotuloBotaoMes(mesAno, mesAtual) {
  return mesAno === mesAtual ? "Planner do mês atual" : "Planner do mês seguinte";
}

function formatarDataDiaSemana(iso) {
  const data = new Date(`${iso}T00:00:00`);
  return `${NOMES_DIA_SEMANA[data.getDay()]}, ${formatarDataBr(iso)}`;
}

// Opção que aparece DEPOIS de gerar uma sugestão em "Plano de Aula IA"
// (ver renderizarPlanoIA) — transforma aquela mesma sugestão (foco/resumo)
// num planner do mês em PDF, pronto pra baixar/enviar por e-mail.
function renderizarPlanner(turma) {
  const expandido = plannerExpandidos.has(turma.id);
  const estado = plannerEstado[turma.id] || { mesAno: proximoMesAno() };
  const iaEstado = planoIaEstado[turma.id] || {};
  const planner = estado.planner;

  return `
    <div>
      <button type="button" class="btn-secundario btn-planner" data-id="${turma.id}">
        ${expandido ? "Esconder Planner de Aulas" : "Gerar Planner de Aulas (PDF) a partir dessa sugestão"}
      </button>

      ${expandido ? `
        <div style="margin-top:12px;">
          <p style="color:#7c8894; font-size:0.85rem; margin-top:0;">
            Gera o planner do mês inteiro (um plano de aula curto pra cada dia de aula da turma), no
            formato pra baixar em PDF ou mandar por e-mail. Não usa IA por conta própria — copia as aulas
            do Plano de Aula IA gerado acima (dias fora dessa sugestão saem no automático, sem IA). Gere o
            Plano de Aula IA primeiro pra aproveitar a sugestão da IA aqui. Depois de gerado, edite o
            conteúdo de qualquer dia à vontade.
          </p>

          <div style="display:flex; flex-wrap:wrap; gap:8px;">
            ${[mesAnoAtual(), proximoMesAno()].map(mesAno => `
              <button type="button" class="btn-secundario btn-escolher-mes-planner ${estado.mesAno === mesAno ? "ativo" : ""}"
                data-turma-id="${turma.id}" data-mes-ano="${mesAno}">
                ${rotuloBotaoMes(mesAno, mesAnoAtual())} (${rotuloMesAno(mesAno)})
              </button>
            `).join("")}
          </div>
          <button type="button" class="btn-gerar-planner" data-id="${turma.id}" style="margin-top:8px;" ${estado.carregando ? "disabled" : ""}>
            ${estado.carregando ? "Gerando..." : (planner ? "Gerar de novo (substitui os dias)" : "Gerar planner")}
          </button>
          <div style="color:#7c8894; font-size:0.78rem; margin-top:4px;">
            Compartilha o mesmo limite do Plano de Aula IA: 2 gerações por dia, por turma.
            ${iaEstado.foco ? ` Foco: ${iaEstado.foco}.` : ""}
          </div>

          ${estado.erro ? `<div class="status-importacao erro" style="margin-top:8px;">${estado.erro}</div>` : ""}
          ${estado.mensagem ? `<div class="status-importacao" style="margin-top:8px;">${estado.mensagem}</div>` : ""}
          ${planner && planner.aviso ? `<div class="status-importacao" style="margin-top:8px;">${planner.aviso}</div>` : ""}

          ${planner ? `
            <div style="margin-top:16px;">
              <strong>Dias de aula (${planner.dias.length}):</strong>
              ${planner.dias.length ? "" : " nenhum dia de aula nesse mês."}
              ${planner.dias.map((d, i) => `
                <div class="cartao-alerta" style="margin-top:8px; padding:12px 14px;">
                  <div class="cartao-alerta-federacao" style="margin-top:0;">${formatarDataDiaSemana(d.data)}</div>
                  <textarea class="planner_dia_conteudo" data-turma-id="${turma.id}" data-indice="${i}"
                    rows="2" maxlength="500" style="margin-top:6px;">${d.conteudo || ""}</textarea>
                </div>
              `).join("")}

              <div class="campo" style="max-width:640px; margin-top:16px;">
                <label>Objetivos do mês</label>
                <textarea class="planner_objetivos" data-turma-id="${turma.id}" rows="2"
                  maxlength="2000" placeholder="ex: preparar 3 atletas pro campeonato estadual">${planner.objetivos || ""}</textarea>
              </div>
              <div class="campo" style="max-width:640px;">
                <label>Anotações</label>
                <textarea class="planner_anotacoes" data-turma-id="${turma.id}" rows="2"
                  maxlength="2000" placeholder="observações livres sobre o mês">${planner.anotacoes || ""}</textarea>
              </div>

              <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">
                <button type="button" class="btn-salvar-planner" data-id="${turma.id}" ${estado.salvando ? "disabled" : ""}>
                  ${estado.salvando ? "Salvando..." : "Salvar alterações"}
                </button>
                <button type="button" class="btn-secundario btn-baixar-planner" data-id="${turma.id}" ${estado.baixando ? "disabled" : ""}>
                  ${estado.baixando ? "Gerando PDF..." : "Baixar PDF"}
                </button>
                <button type="button" class="btn-secundario btn-emailar-planner" data-id="${turma.id}" ${estado.enviando ? "disabled" : ""}>
                  ${estado.enviando ? "Enviando..." : "Enviar por e-mail"}
                </button>
              </div>
            </div>
          ` : ""}
        </div>
      ` : ""}
    </div>
  `;
}

function renderizarTurmas(turmas) {
  turmasAtuais = turmas;

  // Modo "consultar uma turma" (?turma=<id>, veio do submenu): mostra só
  // ela, não a lista inteira — não mistura com as outras.
  const turmasParaExibir = turmaIdFiltro
    ? turmas.filter(t => String(t.id) === String(turmaIdFiltro))
    : turmas;

  if (!turmas.length) {
    elLista.innerHTML = "";
    mostrarStatus("Nenhuma turma criada ainda. Clique em \"+ Nova turma\".");
    return;
  }
  if (turmaIdFiltro && !turmasParaExibir.length) {
    elLista.innerHTML = "";
    mostrarStatus("Essa turma não existe mais.", true);
    return;
  }

  mostrarStatus(turmaIdFiltro ? "" : `${turmas.length} turma(s).`);
  const idParaDestacar = turmaIdFiltro;
  elLista.innerHTML = turmasParaExibir.map(t => {
    const disponiveis = opcoesAlunosDisponiveis(t);
    return `
      <div class="cartao-alerta" data-turma-id="${t.id}" id="turma-${t.id}" style="${idParaDestacar == t.id ? 'outline: 2px solid var(--azul-claro);' : ''}">
        <div class="cartao-alerta-topo">
          <div>
            <h3>${t.nome ? t.nome + " — " : ""}${t.categoria}</h3>
            <div class="cartao-alerta-federacao">${formatarHorario(t.horario_inicio)} às ${formatarHorario(t.horario_fim)}</div>
            ${t.dias_semana.length ? `<div class="cartao-alerta-filtros" style="margin-top:2px;">${t.dias_semana.join(", ")}</div>` : ""}
          </div>
          <div style="display:flex; gap:8px;">
            <button type="button" class="btn-secundario btn-editar-turma" data-id="${t.id}">Editar</button>
            <button type="button" class="btn-remover btn-remover-turma" data-id="${t.id}">Remover</button>
          </div>
        </div>

        <div class="cartao-alerta-filtros">
          <strong>Alunos${t.alunos.length ? ` (${t.alunos.length})` : ""}:</strong>
          ${t.alunos.length ? "" : " nenhum ainda."}
        </div>
        ${t.alunos.length ? `
          <div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">
            ${t.alunos.map(a => `
              <span style="display:inline-flex; align-items:center; gap:6px; background:#eef2f6; border-radius:20px; padding:4px 6px 4px 6px; font-size:0.85rem;">
                ${a.foto_url
                  ? `<img src="${a.foto_url}" alt="" style="width:22px; height:22px; border-radius:50%; object-fit:cover;">`
                  : `<span style="width:22px; height:22px; border-radius:50%; background:#dde5ec; display:inline-flex; align-items:center; justify-content:center; font-size:0.85rem;">🥋</span>`}
                <a href="/meus-alunos/${a.usuario_id}" style="color: var(--azul); text-decoration: none;">${a.nome || "(sem nome)"}</a>
                <button type="button" class="btn-remover-aluno-turma" data-turma-id="${t.id}" data-aluno-id="${a.usuario_id}"
                  style="border:none; background:transparent; color:#b3261e; cursor:pointer; font-size:1rem; line-height:1; padding:2px 4px;">×</button>
              </span>
            `).join("")}
          </div>
        ` : ""}

        <form class="form-add-aluno-turma" data-turma-id="${t.id}" style="display:flex; gap:8px; align-items:flex-end; margin-top:12px;">
          <div class="campo" style="flex:1; margin-bottom:0;">
            <label>Adicionar aluno</label>
            <select ${disponiveis.length ? "" : "disabled"}>
              ${disponiveis.length
                ? disponiveis.map(a => `<option value="${a.usuario_id}">${a.nome || "(sem nome)"}</option>`).join("")
                : `<option value="">${meusAlunos.length ? "Todos os seus alunos já estão nessa turma" : "Você ainda não tem alunos em Meus Alunos"}</option>`}
            </select>
          </div>
          <button type="submit" ${disponiveis.length ? "" : "disabled"}>Adicionar</button>
        </form>

        ${renderizarPlanoAula(t)}
        ${renderizarAulasFuturas(t)}
        ${renderizarPlanoIA(t)}
      </div>
    `;
  }).join("");

  elLista.querySelectorAll(".btn-editar-turma").forEach(btn => {
    btn.addEventListener("click", () => iniciarEdicao(Number(btn.dataset.id), turmas));
  });
  elLista.querySelectorAll(".btn-remover-turma").forEach(btn => {
    btn.addEventListener("click", () => removerTurma(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-remover-aluno-turma").forEach(btn => {
    btn.addEventListener("click", () => removerAlunoDaTurma(Number(btn.dataset.turmaId), Number(btn.dataset.alunoId)));
  });
  elLista.querySelectorAll(".form-add-aluno-turma").forEach(form => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      const select = form.querySelector("select");
      if (!select.value) return;
      adicionarAlunoNaTurma(Number(form.dataset.turmaId), Number(select.value));
    });
  });
  elLista.querySelectorAll(".btn-plano-aula").forEach(btn => {
    btn.addEventListener("click", () => alternarPlanoAula(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-aulas-futuras").forEach(btn => {
    btn.addEventListener("click", () => alternarAulasFuturas(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".form-plano-aula").forEach(form => {
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      salvarPlanoAula(Number(form.dataset.turmaId), form);
    });
  });
  elLista.querySelectorAll(".btn-remover-plano").forEach(btn => {
    btn.addEventListener("click", () => removerPlanoAula(Number(btn.dataset.turmaId), Number(btn.dataset.planoId)));
  });
  elLista.querySelectorAll(".btn-editar-plano").forEach(btn => {
    btn.addEventListener("click", () => editarPlano(Number(btn.dataset.turmaId), Number(btn.dataset.planoId)));
  });
  elLista.querySelectorAll(".btn-cancelar-edicao-plano").forEach(btn => {
    btn.addEventListener("click", () => cancelarEdicaoPlano(Number(btn.dataset.turmaId)));
  });
  elLista.querySelectorAll(".btn-registrar-pendente").forEach(btn => {
    btn.addEventListener("click", () => registrarPendente(Number(btn.dataset.turmaId), btn.dataset.data));
  });
  elLista.querySelectorAll(".historico_mes_ano").forEach(input => {
    input.addEventListener("change", () => {
      mudarMesHistorico(Number(input.dataset.turmaId), input.value);
    });
  });
  elLista.querySelectorAll(".btn-plano-ia").forEach(btn => {
    btn.addEventListener("click", () => alternarPlanoIA(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".plano_ia_foco").forEach(select => {
    select.addEventListener("change", () => {
      const turmaId = Number(select.dataset.turmaId);
      planoIaEstado[turmaId] = { ...(planoIaEstado[turmaId] || {}), foco: select.value };
    });
  });
  elLista.querySelectorAll(".plano_ia_resumo").forEach(textarea => {
    textarea.addEventListener("input", () => {
      const turmaId = Number(textarea.dataset.turmaId);
      planoIaEstado[turmaId] = { ...(planoIaEstado[turmaId] || {}), resumo: textarea.value };
    });
  });
  elLista.querySelectorAll(".btn-gerar-plano-ia").forEach(btn => {
    btn.addEventListener("click", () => gerarPlanoIA(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-salvar-sugestao-ia").forEach(btn => {
    btn.addEventListener("click", () => salvarSugestaoIA(Number(btn.dataset.turmaId), Number(btn.dataset.indice)));
  });
  elLista.querySelectorAll(".btn-salvar-tudo-ia").forEach(btn => {
    btn.addEventListener("click", () => salvarTudoIA(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-planner").forEach(btn => {
    btn.addEventListener("click", () => alternarPlanner(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-escolher-mes-planner").forEach(btn => {
    btn.addEventListener("click", () => {
      const turmaId = Number(btn.dataset.turmaId);
      atualizarEstadoPlanner(turmaId, { mesAno: btn.dataset.mesAno, planner: null, erro: null, mensagem: null });
      carregarPlannerExistente(turmaId);
    });
  });
  elLista.querySelectorAll(".planner_dia_conteudo").forEach(textarea => {
    textarea.addEventListener("input", () => {
      const turmaId = Number(textarea.dataset.turmaId);
      const indice = Number(textarea.dataset.indice);
      const estado = plannerEstado[turmaId];
      if (!estado || !estado.planner) return;
      estado.planner.dias[indice].conteudo = textarea.value;
    });
  });
  elLista.querySelectorAll(".planner_objetivos").forEach(textarea => {
    textarea.addEventListener("input", () => {
      const estado = plannerEstado[Number(textarea.dataset.turmaId)];
      if (estado && estado.planner) estado.planner.objetivos = textarea.value;
    });
  });
  elLista.querySelectorAll(".planner_anotacoes").forEach(textarea => {
    textarea.addEventListener("input", () => {
      const estado = plannerEstado[Number(textarea.dataset.turmaId)];
      if (estado && estado.planner) estado.planner.anotacoes = textarea.value;
    });
  });
  elLista.querySelectorAll(".btn-gerar-planner").forEach(btn => {
    btn.addEventListener("click", () => gerarPlanner(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-salvar-planner").forEach(btn => {
    btn.addEventListener("click", () => salvarPlanner(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-baixar-planner").forEach(btn => {
    btn.addEventListener("click", () => baixarPlannerPdf(Number(btn.dataset.id)));
  });
  elLista.querySelectorAll(".btn-emailar-planner").forEach(btn => {
    btn.addEventListener("click", () => emailarPlanner(Number(btn.dataset.id)));
  });
}

async function carregarTurmas() {
  try {
    await carregarMeusAlunos();
    const resp = await fetchAutenticado("/api/turmas");
    const turmas = await resp.json();
    if (!resp.ok) throw new Error(turmas.erro || "erro ao carregar turmas");
    renderizarTurmas(turmas);
    rolarAteTurmaDestacada();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

function rolarAteTurmaDestacada() {
  const id = new URLSearchParams(window.location.search).get("turma");
  if (!id) return;
  const el = document.getElementById(`turma-${id}`);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function carregarHistorico(turmaId, mesAno) {
  const [ano, mes] = mesAno.split("-").map(Number);
  const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula/historico?mes=${mes}&ano=${ano}`);
  const aulas = await resp.json();
  if (!resp.ok) throw new Error(aulas.erro || "não consegui carregar o histórico");
  historicoPorTurma[turmaId] = { mesAno, aulas };
}

async function carregarPendentes(turmaId) {
  const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula/pendentes`);
  const pendentes = await resp.json();
  if (!resp.ok) throw new Error(pendentes.erro || "não consegui carregar as próximas aulas");
  pendentesPorTurma[turmaId] = pendentes;
}

// Recarrega Histórico/Aulas Futuras só se a seção correspondente estiver
// aberta (senão limpa o cache pra recarregar na próxima vez que abrir) —
// chamado depois de criar/editar/remover uma aula, ou salvar uma sugestão
// do Plano de Aula IA, já que qualquer uma dessas ações pode mudar as
// duas listas (uma aula nova sai da lista de pendentes, por exemplo).
async function atualizarListasAulas(turmaId) {
  const tarefas = [];
  if (planosExpandidos.has(turmaId)) {
    const mesAno = (historicoPorTurma[turmaId] || {}).mesAno || mesAnoAtual();
    tarefas.push(carregarHistorico(turmaId, mesAno));
  } else {
    delete historicoPorTurma[turmaId];
  }
  if (pendentesExpandidos.has(turmaId)) {
    tarefas.push(carregarPendentes(turmaId));
  } else {
    delete pendentesPorTurma[turmaId];
  }
  await Promise.all(tarefas);
}

async function alternarPlanoAula(turmaId) {
  if (planosExpandidos.has(turmaId)) {
    planosExpandidos.delete(turmaId);
    renderizarTurmas(turmasAtuais);
    return;
  }
  await carregarPosicoes();
  try {
    const mesAno = (historicoPorTurma[turmaId] || {}).mesAno || mesAnoAtual();
    await carregarHistorico(turmaId, mesAno);
    planosExpandidos.add(turmaId);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function alternarAulasFuturas(turmaId) {
  if (pendentesExpandidos.has(turmaId)) {
    pendentesExpandidos.delete(turmaId);
    renderizarTurmas(turmasAtuais);
    return;
  }
  try {
    await carregarPendentes(turmaId);
    pendentesExpandidos.add(turmaId);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function mudarMesHistorico(turmaId, mesAno) {
  try {
    await carregarHistorico(turmaId, mesAno);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

function editarPlano(turmaId, planoId) {
  const aula = (historicoPorTurma[turmaId] || { aulas: [] }).aulas.find(p => p.id === planoId);
  if (!aula) return;
  planoEditando[turmaId] = { id: aula.id, data: aula.data, posicoes: aula.posicoes };
  delete planoDataRapida[turmaId];
  renderizarTurmas(turmasAtuais);
}

function cancelarEdicaoPlano(turmaId) {
  delete planoEditando[turmaId];
  renderizarTurmas(turmasAtuais);
}

async function registrarPendente(turmaId, iso) {
  delete planoEditando[turmaId];
  planoDataRapida[turmaId] = iso;

  if (!planosExpandidos.has(turmaId)) {
    await carregarPosicoes();
    try {
      const mesAno = (historicoPorTurma[turmaId] || {}).mesAno || mesAnoAtual();
      await carregarHistorico(turmaId, mesAno);
    } catch (err) {
      mostrarStatus(`Erro: ${err.message}`, true);
      return;
    }
    planosExpandidos.add(turmaId);
  }

  renderizarTurmas(turmasAtuais);
  const elForm = document.querySelector(`.form-plano-aula[data-turma-id="${turmaId}"]`);
  if (elForm) elForm.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function salvarPlanoAula(turmaId, form) {
  const data = form.querySelector(".plano_data").value;
  const posicoes = Array.from(form.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value);
  const editandoId = form.dataset.editandoId;
  if (!posicoes.length) {
    mostrarStatus("Selecione pelo menos uma posição.", true);
    return;
  }
  try {
    const resp = await fetchAutenticado(
      editandoId ? `/api/turmas/${turmaId}/planos-aula/${editandoId}` : `/api/turmas/${turmaId}/planos-aula`,
      {
        method: editandoId ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, posicoes }),
      },
    );
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar a aula");

    delete planoEditando[turmaId];
    delete planoDataRapida[turmaId];
    await atualizarListasAulas(turmaId);
    mostrarStatus(editandoId ? "Aula atualizada!" : "Aula registrada!");
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function removerPlanoAula(turmaId, planoId) {
  if (!confirm("Remover esse registro de aula?")) return;
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula/${planoId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    await atualizarListasAulas(turmaId);
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function alternarPlanoIA(turmaId) {
  if (planoIaExpandidos.has(turmaId)) {
    planoIaExpandidos.delete(turmaId);
    renderizarTurmas(turmasAtuais);
    return;
  }
  await carregarPosicoes();
  planoIaExpandidos.add(turmaId);
  renderizarTurmas(turmasAtuais);
}

async function gerarPlanoIA(turmaId) {
  const estado = planoIaEstado[turmaId] || {};
  planoIaEstado[turmaId] = { ...estado, carregando: true, erro: null };
  renderizarTurmas(turmasAtuais);

  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/plano-ia`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ foco: estado.foco || "", resumo: estado.resumo || "" }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui gerar a sugestão");
    planoIaEstado[turmaId] = { ...estado, carregando: false, erro: null, resultado: dados };
  } catch (err) {
    planoIaEstado[turmaId] = { ...estado, carregando: false, erro: err.message };
  }
  renderizarTurmas(turmasAtuais);
}

async function salvarSugestaoIA(turmaId, indice) {
  const estado = planoIaEstado[turmaId];
  if (!estado || !estado.resultado) return;
  const aula = estado.resultado.aulas[indice];
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planos-aula`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data: aula.data, posicoes: aula.posicoes }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar");
    aula.salvo = true;
    await atualizarListasAulas(turmaId);
    mostrarStatus("Aula salva no histórico!");
    renderizarTurmas(turmasAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function salvarTudoIA(turmaId) {
  const estado = planoIaEstado[turmaId];
  if (!estado || !estado.resultado) return;
  for (let i = 0; i < estado.resultado.aulas.length; i++) {
    if (!estado.resultado.aulas[i].salvo) await salvarSugestaoIA(turmaId, i);
  }
}

function atualizarEstadoPlanner(turmaId, patch) {
  plannerEstado[turmaId] = { ...(plannerEstado[turmaId] || { mesAno: proximoMesAno() }), ...patch };
}

async function alternarPlanner(turmaId) {
  if (plannerExpandidos.has(turmaId)) {
    plannerExpandidos.delete(turmaId);
    renderizarTurmas(turmasAtuais);
    return;
  }
  plannerExpandidos.add(turmaId);
  if (!plannerEstado[turmaId]) {
    plannerEstado[turmaId] = { mesAno: proximoMesAno() };
    await carregarPlannerExistente(turmaId);
    return;
  }
  renderizarTurmas(turmasAtuais);
}

async function carregarPlannerExistente(turmaId) {
  const estado = plannerEstado[turmaId] || { mesAno: proximoMesAno() };
  const [ano, mes] = estado.mesAno.split("-");
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner?mes=${Number(mes)}&ano=${ano}`);
    if (resp.status === 404) {
      atualizarEstadoPlanner(turmaId, { planner: null });
    } else {
      const dados = await resp.json();
      if (!resp.ok) throw new Error(dados.erro || "não consegui carregar o planner");
      atualizarEstadoPlanner(turmaId, { planner: dados });
    }
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

async function gerarPlanner(turmaId) {
  const estado = plannerEstado[turmaId] || { mesAno: proximoMesAno() };
  if (estado.planner && !confirm("Já existe um planner gerado pra esse mês. Gerar de novo substitui o conteúdo de todos os dias (objetivos e anotações são mantidos). Continuar?")) {
    return;
  }
  const iaEstado = planoIaEstado[turmaId] || {};
  // O planner não gera aulas novas com IA — ele copia as aulas já sugeridas
  // pelo Plano de Aula IA (se essa turma já gerou uma). Sem sugestão de IA
  // ainda, o planner sai inteiro no determinístico (sem custo extra).
  const aulasIa = iaEstado.resultado && iaEstado.resultado.ia ? iaEstado.resultado.aulas : null;
  const [ano, mes] = estado.mesAno.split("-");
  atualizarEstadoPlanner(turmaId, { carregando: true, erro: null, mensagem: null });
  renderizarTurmas(turmasAtuais);

  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner?mes=${Number(mes)}&ano=${ano}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ foco: iaEstado.foco || "", aulas_ia: aulasIa }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui gerar o planner");
    atualizarEstadoPlanner(turmaId, { carregando: false, planner: dados });
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { carregando: false, erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

// Salva o estado atual do planner (dias/objetivos/anotações editados na
// tela) no servidor. Reaproveitado pelo botão "Salvar alterações" e,
// antes de baixar/enviar, pra garantir que o PDF/e-mail nunca saia com
// edições que só existiam no navegador (ver baixarPlannerPdf/emailarPlanner).
async function _salvarPlannerNoServidor(turmaId) {
  const estado = plannerEstado[turmaId];
  if (!estado || !estado.planner) return;
  const [ano, mes] = estado.mesAno.split("-");
  const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner?mes=${Number(mes)}&ano=${ano}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dias: estado.planner.dias,
      objetivos: estado.planner.objetivos || "",
      anotacoes: estado.planner.anotacoes || "",
    }),
  });
  const dados = await resp.json();
  if (!resp.ok) throw new Error(dados.erro || "não consegui salvar");
}

async function salvarPlanner(turmaId) {
  const estado = plannerEstado[turmaId];
  if (!estado || !estado.planner) return;
  atualizarEstadoPlanner(turmaId, { salvando: true, erro: null, mensagem: null });
  renderizarTurmas(turmasAtuais);

  try {
    await _salvarPlannerNoServidor(turmaId);
    atualizarEstadoPlanner(turmaId, { salvando: false, mensagem: "Alterações salvas!" });
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { salvando: false, erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

async function baixarPlannerPdf(turmaId) {
  const estado = plannerEstado[turmaId];
  if (!estado || !estado.planner) return;
  const [ano, mes] = estado.mesAno.split("-");
  atualizarEstadoPlanner(turmaId, { baixando: true, erro: null });
  renderizarTurmas(turmasAtuais);

  try {
    await _salvarPlannerNoServidor(turmaId);
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner/pdf?mes=${Number(mes)}&ano=${ano}`);
    if (!resp.ok) {
      const dados = await resp.json().catch(() => ({}));
      throw new Error(dados.erro || "não consegui gerar o PDF");
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `planner-${mes}-${ano}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    atualizarEstadoPlanner(turmaId, { baixando: false });
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { baixando: false, erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

async function emailarPlanner(turmaId) {
  const estado = plannerEstado[turmaId];
  if (!estado || !estado.planner) return;
  const [ano, mes] = estado.mesAno.split("-");
  atualizarEstadoPlanner(turmaId, { enviando: true, erro: null, mensagem: null });
  renderizarTurmas(turmasAtuais);

  try {
    await _salvarPlannerNoServidor(turmaId);
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/planner/email?mes=${Number(mes)}&ano=${ano}`, {
      method: "POST",
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui enviar o e-mail");
    atualizarEstadoPlanner(turmaId, { enviando: false, mensagem: `Planner enviado para ${dados.email}!` });
  } catch (err) {
    atualizarEstadoPlanner(turmaId, { enviando: false, erro: err.message });
  }
  renderizarTurmas(turmasAtuais);
}

function iniciarEdicao(turmaId, turmas) {
  const turma = turmas.find(t => t.id === turmaId);
  if (!turma) return;
  elTurmaId.value = turma.id;
  elNome.value = turma.nome || "";
  elCategoria.value = turma.categoria;
  elInicio.value = formatarHorario(turma.horario_inicio);
  elFim.value = formatarHorario(turma.horario_fim);
  elDiasSemana.querySelectorAll('input[type="checkbox"]').forEach(c => {
    c.checked = turma.dias_semana.includes(c.value);
  });
  elTituloForm.textContent = "Editar turma";
  elBtnSalvar.textContent = "Salvar alterações";
  elBtnCancelar.style.display = "";
  // Editar abre o formulário mesmo estando no modo "consultar" — as duas
  // funcionalidades continuam sem se misturar na tela (a lista some
  // enquanto o formulário de edição está aberto).
  elSecaoForm.style.display = "";
  elSecaoLista.style.display = "none";
  elForm.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicao() {
  elTurmaId.value = "";
  elForm.reset();
  elTituloForm.textContent = "Nova turma";
  elBtnSalvar.textContent = "Criar turma";
  elBtnCancelar.style.display = "none";
  if (!modoNovaTurma) aplicarModoPagina();
}

elBtnCancelar.addEventListener("click", cancelarEdicao);

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = {
    nome: elNome.value,
    categoria: elCategoria.value,
    horario_inicio: elInicio.value,
    horario_fim: elFim.value,
    dias_semana: Array.from(elDiasSemana.querySelectorAll('input[type="checkbox"]:checked')).map(c => c.value),
  };
  const editando = elTurmaId.value;
  try {
    const resp = await fetchAutenticado(editando ? `/api/turmas/${editando}` : "/api/turmas", {
      method: editando ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    const dadosResp = await resp.json();
    if (!resp.ok) throw new Error(dadosResp.erro || "não consegui salvar a turma");
    if (!editando) {
      // Turma nova: manda direto pra tela de consulta dela, já separada
      // da criação (em vez de ficar preso na tela de "Nova turma").
      window.location.href = `/turmas?turma=${dadosResp.id}`;
      return;
    }
    mostrarStatus("Turma atualizada!");
    cancelarEdicao();
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});

async function removerTurma(turmaId) {
  if (!confirm("Remover essa turma? Os alunos continuam em Meus Alunos.")) return;
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    if (elTurmaId.value === String(turmaId)) cancelarEdicao();
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function adicionarAlunoNaTurma(turmaId, alunoId) {
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/alunos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aluno_id: alunoId }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui adicionar o aluno");
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function removerAlunoDaTurma(turmaId, alunoId) {
  try {
    const resp = await fetchAutenticado(`/api/turmas/${turmaId}/alunos/${alunoId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover o aluno");
    carregarTurmas();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregarTurmas();
