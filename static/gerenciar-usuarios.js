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

const elCardOrigemTrafego = document.getElementById("card-origem-trafego");
const elListaOrigemTrafego = document.getElementById("lista-origem-trafego");

// Agrupa client-side por utm_campaign (ou utm_source, se a campanha não
// veio) — só conta quem tem ALGUMA origem capturada (ver
// auth-nav.js::capturarOrigemTrafego); cadastros sem isso (a maioria, até
// o anúncio estar configurado com "Parâmetros de URL") ficam de fora da
// contagem, não aparecem como "Direto" nem nada parecido, pra não dar a
// falsa impressão de que a origem é conhecida quando não é.
function renderizarOrigemTrafego(usuarios) {
  const comOrigem = usuarios.filter(u => u.utm_campaign || u.utm_source);
  if (!comOrigem.length) {
    elCardOrigemTrafego.style.display = "none";
    return;
  }
  const contagem = new Map();
  comOrigem.forEach(u => {
    const chave = u.utm_campaign || u.utm_source;
    contagem.set(chave, (contagem.get(chave) || 0) + 1);
  });
  const ordenado = [...contagem.entries()].sort((a, b) => b[1] - a[1]);
  elListaOrigemTrafego.innerHTML = ordenado.map(([nome, qtd]) => `<li><strong>${qtd}</strong> — ${nome}</li>`).join("");
  elCardOrigemTrafego.style.display = "block";
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
    elCorpoTabela.innerHTML = '<tr><td colspan="10">Nenhum usuário encontrado.</td></tr>';
    return;
  }
  elCorpoTabela.innerHTML = usuarios.map(u => `
    <tr>
      <td><input type="checkbox" class="chk-usuario" data-id="${u.id}" ${idsSelecionados.has(u.id) ? "checked" : ""}></td>
      <td><button type="button" class="link-detalhes-usuario btn-link" data-id="${u.id}" title="Ver detalhes">${u.email}</button></td>
      <td>${u.nome_usuario || "—"}</td>
      <td>${badgeTipo(u)}</td>
      <td>${badgePlano(u.plano)}</td>
      <td>${badgeAssinatura(u)}</td>
      <td>${formatarData(u.criado_em)}</td>
      <td style="text-align:center;">${u.alertas || 0}</td>
      <td>${u.campanha_email_enviado_em ? formatarData(u.campanha_email_enviado_em) : "—"}</td>
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
  if (botaoMenu) {
    ev.stopPropagation(); // não deixa o listener de "clicar fora" (abaixo) fechar na mesma hora
    const usuario = usuariosCarregados.find(u => String(u.id) === botaoMenu.dataset.id);
    if (usuario) abrirMenuAcoes(usuario, botaoMenu);
    return;
  }
  const botaoDetalhes = ev.target.closest(".link-detalhes-usuario");
  if (botaoDetalhes) abrirDetalhesUsuario(Number(botaoDetalhes.dataset.id));
});

// --- Modal "Ver detalhes" (pagamento + recursos já usados) -----------------
const elModalDetalhes = document.getElementById("modal-detalhes-usuario");
const elDetalhesTitulo = document.getElementById("detalhes-titulo");
const elDetalhesConteudo = document.getElementById("detalhes-conteudo");

const LABEL_RECURSOS = {
  perfil_carreira: "Preencheu o perfil em Minha Carreira",
  competicoes_registradas: "Competições registradas em Minha Carreira",
  alertas_criados: "Alertas criados",
  itens_agenda: "Itens já marcados em Minha Agenda",
  turmas_criadas: "Turmas criadas (Mestre)",
  filtro_padrao_salvo: "Salvou um filtro padrão no Radar de Atletas",
};

function formatarDataHora(timestampSegundos) {
  if (!timestampSegundos) return null;
  return new Date(Number(timestampSegundos) * 1000).toLocaleDateString("pt-BR");
}

function renderizarDetalhes(dados) {
  const { usuario, pagamento, recursos, origem_trafego } = dados;
  elDetalhesTitulo.textContent = usuario.nome_usuario || usuario.email;

  let blocoOrigem = "";
  if (origem_trafego) {
    const partes = [];
    if (origem_trafego.utm_source) partes.push(`<li><strong>Origem:</strong> ${origem_trafego.utm_source}</li>`);
    if (origem_trafego.utm_medium) partes.push(`<li><strong>Mídia:</strong> ${origem_trafego.utm_medium}</li>`);
    if (origem_trafego.utm_campaign) partes.push(`<li><strong>Campanha:</strong> ${origem_trafego.utm_campaign}</li>`);
    if (origem_trafego.fbclid) partes.push(`<li><strong>Veio de um anúncio do Meta</strong> (clique rastreado)</li>`);
    if (origem_trafego.gclid) partes.push(`<li><strong>Veio de um anúncio do Google</strong> (clique rastreado)</li>`);
    blocoOrigem = `
      <h3 style="color:var(--azul); font-size:1rem; margin-bottom:6px;">Origem do cadastro</h3>
      <ul style="margin:0 0 16px; padding-left:20px; color:var(--texto);">${partes.join("")}</ul>
    `;
  }

  let blocoPagamento;
  if (!pagamento) {
    blocoPagamento = `<p style="color:#55606b;">Nunca teve nenhuma assinatura (continua no Plano Free).</p>`;
  } else {
    const vencimento = formatarDataHora(pagamento.periodo_atual_fim);
    blocoPagamento = `
      <ul style="margin:0 0 16px; padding-left:20px; color:var(--texto);">
        <li><strong>Forma de pagamento:</strong> ${pagamento.forma_label}</li>
        <li><strong>Situação:</strong> ${pagamento.eh_teste_gratis ? "Em teste grátis (ainda não pagou)" : LABEL_STATUS[pagamento.status] || pagamento.status}</li>
        <li><strong>Plano:</strong> ${pagamento.plano === "mestre" ? "Mestre PRO" : "Atleta PRO"}${pagamento.periodicidade ? ` (${LABEL_PERIODICIDADE[pagamento.periodicidade] || pagamento.periodicidade})` : ""}</li>
        ${vencimento ? `<li><strong>Vencimento do período atual:</strong> ${vencimento}</li>` : ""}
      </ul>
    `;
  }

  const itensRecursos = Object.entries(LABEL_RECURSOS).map(([chave, label]) => {
    const valor = recursos[chave];
    const usou = typeof valor === "boolean" ? valor : valor > 0;
    const sufixo = typeof valor === "number" ? ` (${valor})` : "";
    return `<li style="color:${usou ? "var(--texto)" : "#8a94a3"};">${usou ? "✅" : "⬜"} ${label}${usou ? sufixo : ""}</li>`;
  }).join("");

  elDetalhesConteudo.innerHTML = `
    <p style="color:#55606b; font-size:0.85rem; margin-top:-8px;">${usuario.email} · cadastrado em ${formatarData(usuario.criado_em)}</p>
    <h3 style="color:var(--azul); font-size:1rem; margin-bottom:6px;">Pagamento</h3>
    ${blocoPagamento}
    ${blocoOrigem}
    <h3 style="color:var(--azul); font-size:1rem; margin-bottom:6px;">Recursos já utilizados</h3>
    <ul style="margin:0; padding-left:0; list-style:none; display:flex; flex-direction:column; gap:6px;">
      ${itensRecursos}
    </ul>
  `;
}

async function abrirDetalhesUsuario(usuarioId) {
  elModalDetalhes.style.display = "flex";
  elDetalhesTitulo.textContent = "Carregando...";
  elDetalhesConteudo.innerHTML = "";
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuarioId}/detalhes`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar detalhes");
    renderizarDetalhes(dados);
  } catch (err) {
    elDetalhesTitulo.textContent = "Erro";
    elDetalhesConteudo.innerHTML = `<p style="color:#b3261e;">${err.message}</p>`;
  }
}

document.getElementById("btn-fechar-detalhes").addEventListener("click", () => {
  elModalDetalhes.style.display = "none";
});
elModalDetalhes.addEventListener("click", (ev) => {
  if (ev.target === elModalDetalhes) elModalDetalhes.style.display = "none";
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

    const descadastrados = dados.resultados.filter(r => r.descadastrado);
    const falhas = dados.resultados.filter(r => !r.enviado && !r.descadastrado);
    const enviados = dados.resultados.length - falhas.length - descadastrados.length;
    let texto = `E-mail enviado pra ${enviados} pessoa(s)!`;
    if (descadastrados.length) texto += ` ${descadastrados.length} pulada(s) por já ter descadastrado.`;
    if (falhas.length) texto += ` Falhou pra: ${falhas.map(f => f.email || f.usuario_id).join(", ")}`;
    elStatusAvulso.textContent = texto;
    elStatusAvulso.className = "status-importacao" + (falhas.length ? " erro" : "");
  } catch (err) {
    elStatusAvulso.textContent = `Erro: ${err.message}`;
    elStatusAvulso.className = "status-importacao erro";
  } finally {
    elBtnEnviarEmailAvulso.disabled = idsSelecionados.size === 0;
  }
});

const elStatusAcoesUsuarios = document.getElementById("status-acoes-usuarios");

// Marca pra seleção todo mundo que ainda não tem campanha_email_enviado_em
// (nunca recebeu um disparo de "Enviar e-mail avulso") — sem isso não tinha
// como saber quem já tinha sido mandado nas rodadas anteriores e quem
// sobrou (pedido do usuário, 24/10/2026).
document.getElementById("btn-selecionar-sem-campanha").addEventListener("click", () => {
  const semCampanha = usuariosCarregados.filter(u => !u.campanha_email_enviado_em);
  semCampanha.forEach(u => idsSelecionados.add(u.id));
  atualizarSelecaoUI();
  aplicarFiltro();
  elStatusAcoesUsuarios.textContent = `${semCampanha.length} usuário(s) nunca receberam e-mail de campanha — selecionados.`;
  elStatusAcoesUsuarios.className = "status-importacao";
});

document.getElementById("btn-conceder-teste-retroativo").addEventListener("click", async (ev) => {
  if (!confirm("Conceder 7 dias de teste grátis do Plano PRO a TODOS os usuários Free sem nenhuma assinatura? A contagem começa agora mesmo pra cada um.")) return;
  const botao = ev.target;
  botao.disabled = true;
  elStatusAcoesUsuarios.textContent = "Concedendo...";
  elStatusAcoesUsuarios.className = "status-importacao";
  try {
    const resp = await fetchAutenticado("/api/usuarios/conceder-teste-gratis-retroativo", { method: "POST" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui conceder o teste grátis");
    elStatusAcoesUsuarios.textContent = `${dados.concedidos} conta(s) receberam o teste grátis agora.`;
    await carregarUsuarios();
  } catch (err) {
    elStatusAcoesUsuarios.textContent = `Erro: ${err.message}`;
    elStatusAcoesUsuarios.className = "status-importacao erro";
  } finally {
    botao.disabled = false;
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
    renderizarOrigemTrafego(usuariosCarregados);
    renderizarTabela(usuariosCarregados);
    mostrarStatus("");
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

elFiltroBusca.addEventListener("input", aplicarFiltro);

carregarUsuarios();
