const elStatus = document.getElementById("status");
const elGradeResumo = document.getElementById("grade-resumo");
const elCorpoTabela = document.getElementById("corpo-tabela-usuarios");
const elFiltroBusca = document.getElementById("filtro-busca");

const LABEL_STATUS = {
  trialing: "Teste grátis",
  active: "Ativa",
  past_due: "Pagamento pendente",
  canceled: "Cancelada",
};

let usuariosCarregados = [];
const idsSelecionados = new Set();

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarData(data) {
  if (!data) return "";
  return new Date(data.replace(" ", "T") + "Z").toLocaleDateString("pt-BR");
}

const LABEL_PERIODICIDADE = { mensal: "mensal", anual: "anual" };

function badgeAssinatura(usuario) {
  if (!usuario.assinatura_status) {
    return '<span class="badge-inscricao badge-desconhecida">Sem assinatura</span>';
  }
  const label = LABEL_STATUS[usuario.assinatura_status] || usuario.assinatura_status;
  const classe = usuario.assinatura_status === "active" || usuario.assinatura_status === "trialing"
    ? "badge-aberta" : "badge-fechada";
  // Periodicidade (mensal/anual) junto do plano, ex: "Teste grátis (mestre · anual)"
  // — sem PIX, onde não existe periodicidade salva (pagamento avulso, não
  // recorrente), essa parte simplesmente some.
  const periodicidade = usuario.assinatura_periodicidade
    ? ` · ${LABEL_PERIODICIDADE[usuario.assinatura_periodicidade] || usuario.assinatura_periodicidade}`
    : "";
  const plano = usuario.assinatura_plano ? ` (${usuario.assinatura_plano}${periodicidade})` : "";
  return `<span class="badge-inscricao ${classe}">${label}${plano}</span>`;
}

function renderizarResumo(resumo) {
  const cards = [
    { label: "Total de contas", value: resumo.total },
    { label: "Atleta PRO", value: resumo.por_plano["Atleta PRO"] || 0 },
    { label: "Mestre PRO", value: resumo.por_plano["Mestre PRO"] || 0 },
    { label: "Em teste grátis", value: resumo.por_status_assinatura.trialing || 0 },
    { label: "Assinatura ativa", value: resumo.por_status_assinatura.active || 0 },
    { label: "Pagamento pendente", value: resumo.por_status_assinatura.past_due || 0 },
    { label: "Canceladas", value: resumo.por_status_assinatura.canceled || 0 },
    { label: "Sem assinatura", value: resumo.por_status_assinatura.sem_assinatura || 0 },
  ];
  elGradeResumo.innerHTML = cards.map(c => `
    <div class="stat-box">
      <div class="stat-value">${c.value}</div>
      <div class="stat-label">${c.label}</div>
    </div>`).join("");
}

function contaEhFree(u) {
  return !["trialing", "active", "past_due"].includes(u.assinatura_status);
}

// "Mestre" ou "Atleta" — prioriza o plano REAL (o que a pessoa paga de
// verdade, assinatura_plano) sobre o que ela escolheu no cadastro
// (tipo_perfil), que pode estar desatualizado (ex: assinou Mestre PRO sem
// nunca ter marcado "Mestre" no cadastro, ou o contrário). Sem assinatura
// nenhuma, cai pro que foi declarado no cadastro mesmo, único dado que
// sobra pra alguém no Free.
function badgeTipo(u) {
  const tipo = u.assinatura_plano || u.tipo_perfil;
  if (!tipo) return "—";
  const rotulo = tipo === "mestre" ? "Mestre" : "Atleta";
  return `<span class="badge-inscricao badge-desconhecida">${rotulo}</span>`;
}

function badgePlano(plano) {
  const classe = plano === "Atleta PRO" || plano === "Mestre PRO"
    ? "badge-aberta"
    : plano === "E-mail não confirmado" ? "badge-fechada" : "badge-desconhecida";
  return `<span class="badge-inscricao ${classe}">${plano}</span>`;
}

function renderizarTabela(usuarios) {
  if (!usuarios.length) {
    elCorpoTabela.innerHTML = '<tr><td colspan="9">Nenhum usuário encontrado.</td></tr>';
    return;
  }
  elCorpoTabela.innerHTML = usuarios.map(u => `
    <tr>
      <td><input type="checkbox" class="chk-usuario" data-id="${u.id}" ${idsSelecionados.has(u.id) ? "checked" : ""}></td>
      <td>${u.email}</td>
      <td>${u.nome_usuario || "—"}</td>
      <td>${badgeTipo(u)}</td>
      <td>${badgePlano(u.plano)}</td>
      <td>${badgeAssinatura(u)}</td>
      <td>${formatarData(u.criado_em)}</td>
      <td style="text-align:center;">${u.alertas || 0}</td>
      <td><button type="button" class="btn-secundario btn-menu-acoes" data-id="${u.id}" title="Ações">⋮</button></td>
    </tr>
  `).join("");
}

// Todos os botões de ação (Tornar Mestre/Atleta, Editar e-mail, Reenviar
// confirmação, Apagar) ficavam soltos na linha — com a coluna de Plano/
// Assinatura/Alertas já preenchendo a tabela, virava uma fileira enorme
// de botões por usuário. Agora ficam atrás de um "⋮" só, num menu que
// abre por cima da tabela (position:fixed, calculado igual o submenu do
// menu principal do site — foge do overflow-x:auto da tabela, que corta
// qualquer dropdown position:absolute).
let elMenuAcoesAberto = null;

function fecharMenuAcoes() {
  if (elMenuAcoesAberto) {
    elMenuAcoesAberto.remove();
    elMenuAcoesAberto = null;
  }
}

function abrirMenuAcoes(usuario, botao) {
  fecharMenuAcoes();

  const menu = document.createElement("div");
  menu.className = "menu-acoes-usuario";
  menu.innerHTML = `
    <button type="button" class="item-acao" data-acao="email">Editar e-mail</button>
    ${!usuario.email_verificado ? `<button type="button" class="item-acao" data-acao="reenviar">Reenviar confirmação</button>` : ""}
    ${!usuario.email_verificado ? `<button type="button" class="item-acao" data-acao="confirmar-manual">Marcar como confirmado</button>` : ""}
    ${contaEhFree(usuario) ? `<button type="button" class="item-acao" data-acao="liberar-pro">Liberar Plano PRO</button>` : ""}
    ${contaEhFree(usuario) ? `<button type="button" class="item-acao item-acao-perigo" data-acao="apagar">Apagar</button>` : ""}
  `;
  document.body.appendChild(menu);

  const r = botao.getBoundingClientRect();
  const largura = menu.offsetWidth;
  const altura = menu.offsetHeight;
  menu.style.top = `${Math.max(8, Math.min(r.bottom + 4, window.innerHeight - altura - 8))}px`;
  menu.style.left = `${Math.max(8, Math.min(r.right - largura, window.innerWidth - largura - 8))}px`;

  menu.addEventListener("click", (ev) => {
    const item = ev.target.closest(".item-acao");
    if (!item) return;
    fecharMenuAcoes();
    if (item.dataset.acao === "email") editarEmail(usuario, botao);
    else if (item.dataset.acao === "reenviar") reenviarConfirmacao(usuario, botao);
    else if (item.dataset.acao === "confirmar-manual") confirmarEmailManualmente(usuario, botao);
    else if (item.dataset.acao === "liberar-pro") liberarPlanoPro(usuario, botao);
    else if (item.dataset.acao === "apagar") apagarUsuario(usuario, botao);
  });

  elMenuAcoesAberto = menu;
}

document.addEventListener("click", (ev) => {
  if (!elMenuAcoesAberto) return;
  if (elMenuAcoesAberto.contains(ev.target) || ev.target.closest(".btn-menu-acoes")) return;
  fecharMenuAcoes();
});

async function editarEmail(usuario, botao) {
  const novoEmail = prompt(`Corrigir o e-mail de ${usuario.email} para:`, usuario.email);
  if (!novoEmail || novoEmail.trim().toLowerCase() === usuario.email.toLowerCase()) return;

  botao.disabled = true;
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuario.id}/email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: novoEmail.trim() }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao alterar e-mail");
    mostrarStatus(`E-mail corrigido para ${dados.email} — link de confirmação reenviado.`);
    await carregarUsuarios();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
    botao.disabled = false;
  }
}

async function confirmarEmailManualmente(usuario, botao) {
  if (!confirm(`Confirmar o e-mail de ${usuario.email} manualmente, sem esperar o link? Use quando a pessoa não recebe o e-mail (comum com Hotmail/Outlook, que filtram bastante).`)) return;

  botao.disabled = true;
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuario.id}/confirmar-email-manualmente`, { method: "POST" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao confirmar e-mail");
    mostrarStatus(`E-mail de ${usuario.email} confirmado manualmente.`);
    await carregarUsuarios();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
    botao.disabled = false;
  }
}

async function liberarPlanoPro(usuario, botao) {
  const plano = prompt(`Liberar qual plano pra ${usuario.email}? Digite "atleta" ou "mestre".`, "atleta");
  if (!plano) return;
  const planoNormalizado = plano.trim().toLowerCase();
  if (!["atleta", "mestre"].includes(planoNormalizado)) {
    mostrarStatus('Plano inválido — digite "atleta" ou "mestre".', true);
    return;
  }

  const diasTexto = prompt('Por quantos dias? Deixe em branco para sem validade (fica até você mesmo revogar).', "30");
  if (diasTexto === null) return;
  let dias = null;
  if (diasTexto.trim() !== "") {
    dias = parseInt(diasTexto.trim(), 10);
    if (!Number.isInteger(dias) || dias <= 0) {
      mostrarStatus("Número de dias inválido.", true);
      return;
    }
  }

  const rotuloPlano = planoNormalizado === "atleta" ? "Atleta PRO" : "Mestre PRO";
  const rotuloValidade = dias ? `por ${dias} dia(s)` : "sem validade definida";
  if (!confirm(`Liberar o Plano ${rotuloPlano} pra ${usuario.email}, ${rotuloValidade}?`)) return;

  botao.disabled = true;
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuario.id}/liberar-plano-pro`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plano: planoNormalizado, dias }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao liberar o plano");
    mostrarStatus(`Plano ${rotuloPlano} liberado pra ${usuario.email}.`);
    await carregarUsuarios();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
    botao.disabled = false;
  }
}

async function reenviarConfirmacao(usuario, botao) {
  botao.disabled = true;
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuario.id}/reenviar-confirmacao`, { method: "POST" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao reenviar confirmação");
    mostrarStatus(dados.email_enviado ? `Confirmação reenviada pra ${usuario.email}.` : `Conta atualizada, mas o envio do e-mail falhou — tenta de novo em alguns minutos.`, !dados.email_enviado);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  } finally {
    botao.disabled = false;
  }
}

async function apagarUsuario(usuario, botao) {
  if (!confirm(`Apagar a conta de ${usuario.email}? Essa ação não pode ser desfeita.`)) return;

  botao.disabled = true;
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuario.id}`, { method: "DELETE" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao apagar usuário");
    await carregarUsuarios();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
    botao.disabled = false;
  }
}

elCorpoTabela.addEventListener("click", (ev) => {
  const botaoMenu = ev.target.closest(".btn-menu-acoes");
  if (!botaoMenu) return;
  ev.stopPropagation(); // não deixa o listener de "clicar fora" (abaixo) fechar na mesma hora
  const usuario = usuariosCarregados.find(u => String(u.id) === botaoMenu.dataset.id);
  if (usuario) abrirMenuAcoes(usuario, botaoMenu);
});

const elTextoSelecionados = document.getElementById("texto-selecionados");
const elBtnEnviarEmailAvulso = document.getElementById("btn-enviar-email-avulso");

function atualizarSelecaoUI() {
  elBtnEnviarEmailAvulso.disabled = idsSelecionados.size === 0;
  elTextoSelecionados.textContent = idsSelecionados.size
    ? `${idsSelecionados.size} usuário(s) selecionado(s) pra receber o e-mail.`
    : "Marque um ou mais usuários na tabela acima pra habilitar o envio.";
}

elCorpoTabela.addEventListener("change", (ev) => {
  const chk = ev.target.closest(".chk-usuario");
  if (!chk) return;
  const id = Number(chk.dataset.id);
  if (chk.checked) idsSelecionados.add(id); else idsSelecionados.delete(id);
  atualizarSelecaoUI();
});

elBtnEnviarEmailAvulso.addEventListener("click", async () => {
  const assunto = document.getElementById("email_avulso_assunto").value.trim();
  const corpo = document.getElementById("email_avulso_corpo").value.trim();
  if (!assunto || !corpo) {
    mostrarStatus("Preencha o assunto e o corpo do e-mail.", true);
    return;
  }
  const destinatarios = usuariosCarregados.filter(u => idsSelecionados.has(u.id)).map(u => u.email);
  if (!confirm(`Enviar esse e-mail pra ${destinatarios.length} pessoa(s)?\n\n${destinatarios.join("\n")}`)) return;

  const elStatusAvulso = document.getElementById("status-email-avulso");
  elBtnEnviarEmailAvulso.disabled = true;
  elStatusAvulso.textContent = "Enviando...";
  elStatusAvulso.className = "status-importacao";
  try {
    const resp = await fetchAutenticado("/api/usuarios/enviar-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario_ids: [...idsSelecionados], assunto, corpo }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao enviar e-mail");

    const falhas = dados.resultados.filter(r => !r.enviado);
    elStatusAvulso.textContent = falhas.length
      ? `Enviado pra ${dados.resultados.length - falhas.length} de ${dados.resultados.length} — falhou pra: ${falhas.map(f => f.email || f.usuario_id).join(", ")}`
      : `E-mail enviado pra ${dados.resultados.length} pessoa(s)!`;
    elStatusAvulso.className = "status-importacao" + (falhas.length ? " erro" : "");
  } catch (err) {
    elStatusAvulso.textContent = `Erro: ${err.message}`;
    elStatusAvulso.className = "status-importacao erro";
  } finally {
    elBtnEnviarEmailAvulso.disabled = idsSelecionados.size === 0;
  }
});

function aplicarFiltro() {
  const termo = elFiltroBusca.value.trim().toLowerCase();
  if (!termo) {
    renderizarTabela(usuariosCarregados);
    return;
  }
  const filtrados = usuariosCarregados.filter(u =>
    u.email.toLowerCase().includes(termo) || (u.nome_usuario || "").toLowerCase().includes(termo)
  );
  renderizarTabela(filtrados);
}

async function carregarUsuarios() {
  mostrarStatus("Carregando...");
  try {
    const resp = await fetchAutenticado("/api/usuarios");
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar usuários");

    usuariosCarregados = dados.usuarios;
    renderizarResumo(dados.resumo);
    renderizarTabela(usuariosCarregados);
    mostrarStatus("");
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

elFiltroBusca.addEventListener("input", aplicarFiltro);

carregarUsuarios();
