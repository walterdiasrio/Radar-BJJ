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

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarData(data) {
  if (!data) return "";
  return new Date(data.replace(" ", "T") + "Z").toLocaleDateString("pt-BR");
}

function badgeAssinatura(usuario) {
  if (!usuario.assinatura_status) {
    return '<span class="badge-inscricao badge-desconhecida">Sem assinatura</span>';
  }
  const label = LABEL_STATUS[usuario.assinatura_status] || usuario.assinatura_status;
  const classe = usuario.assinatura_status === "active" || usuario.assinatura_status === "trialing"
    ? "badge-aberta" : "badge-fechada";
  const plano = usuario.assinatura_plano ? ` (${usuario.assinatura_plano})` : "";
  return `<span class="badge-inscricao ${classe}">${label}${plano}</span>`;
}

function renderizarResumo(resumo) {
  const cards = [
    { label: "Total de contas", value: resumo.total },
    { label: "Perfil Atleta", value: resumo.por_perfil.atleta || 0 },
    { label: "Perfil Mestre", value: resumo.por_perfil.mestre || 0 },
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

function badgePlano(plano) {
  const classe = plano === "Atleta PRO" || plano === "Mestre PRO"
    ? "badge-aberta"
    : plano === "E-mail não confirmado" ? "badge-fechada" : "badge-desconhecida";
  return `<span class="badge-inscricao ${classe}">${plano}</span>`;
}

function renderizarTabela(usuarios) {
  if (!usuarios.length) {
    elCorpoTabela.innerHTML = '<tr><td colspan="7">Nenhum usuário encontrado.</td></tr>';
    return;
  }
  elCorpoTabela.innerHTML = usuarios.map(u => {
    const novoPerfil = u.tipo_perfil === "mestre" ? "atleta" : "mestre";
    const botaoApagar = contaEhFree(u)
      ? `<button type="button" class="btn-secundario btn-apagar-usuario" data-id="${u.id}" style="color:#c0392b;">Apagar</button>`
      : "";
    return `
    <tr>
      <td>${u.email}</td>
      <td>${u.tipo_perfil === "mestre" ? "Mestre" : "Atleta"}</td>
      <td>${u.nome_usuario || "—"}</td>
      <td>${badgePlano(u.plano)}</td>
      <td>${badgeAssinatura(u)}</td>
      <td>${formatarData(u.criado_em)}</td>
      <td>
        <button type="button" class="btn-secundario btn-alternar-perfil" data-id="${u.id}" data-novo-perfil="${novoPerfil}">Tornar ${novoPerfil === "mestre" ? "Mestre" : "Atleta"}</button>
        <button type="button" class="btn-secundario btn-editar-email" data-id="${u.id}">Editar e-mail</button>
        ${botaoApagar}
      </td>
    </tr>
  `;
  }).join("");
}

async function alternarPerfil(usuario, novoPerfil, botao) {
  const rotulo = novoPerfil === "mestre" ? "Mestre" : "Atleta";
  if (!confirm(`Mudar o perfil de ${usuario.email} para ${rotulo}?`)) return;

  botao.disabled = true;
  try {
    const resp = await fetchAutenticado(`/api/usuarios/${usuario.id}/tipo-perfil`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo_perfil: novoPerfil }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao mudar o perfil");
    await carregarUsuarios();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
    botao.disabled = false;
  }
}

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
  const botaoPerfil = ev.target.closest(".btn-alternar-perfil");
  if (botaoPerfil) {
    const usuario = usuariosCarregados.find(u => String(u.id) === botaoPerfil.dataset.id);
    if (usuario) alternarPerfil(usuario, botaoPerfil.dataset.novoPerfil, botaoPerfil);
    return;
  }
  const botaoEmail = ev.target.closest(".btn-editar-email");
  if (botaoEmail) {
    const usuario = usuariosCarregados.find(u => String(u.id) === botaoEmail.dataset.id);
    if (usuario) editarEmail(usuario, botaoEmail);
    return;
  }
  const botaoApagar = ev.target.closest(".btn-apagar-usuario");
  if (botaoApagar) {
    const usuario = usuariosCarregados.find(u => String(u.id) === botaoApagar.dataset.id);
    if (usuario) apagarUsuario(usuario, botaoApagar);
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
