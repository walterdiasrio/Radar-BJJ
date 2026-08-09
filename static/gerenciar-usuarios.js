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

function renderizarTabela(usuarios) {
  if (!usuarios.length) {
    elCorpoTabela.innerHTML = '<tr><td colspan="5">Nenhum usuário encontrado.</td></tr>';
    return;
  }
  elCorpoTabela.innerHTML = usuarios.map(u => `
    <tr>
      <td>${u.email}</td>
      <td>${u.tipo_perfil === "mestre" ? "Mestre" : "Atleta"}</td>
      <td>${u.nome_usuario || "—"}</td>
      <td>${badgeAssinatura(u)}</td>
      <td>${formatarData(u.criado_em)}</td>
    </tr>
  `).join("");
}

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
