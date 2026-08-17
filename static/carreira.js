// ---------- Abas internas ----------
// Perfil é liberado pro Plano Free — as outras abas (aqui embaixo) exigem
// assinatura; sem ela, ficam bloqueadas com o banner do Plano PRO
// correspondente em vez do conteúdo real (ver aplicarBloqueioPro).
const ABAS_COM_ASSINATURA = new Set(["registrar", "historico", "pesquisa", "estatisticas", "compartilhar"]);
let temAssinaturaCarreira = true; // otimista até checarSessaoCarreira() responder

document.querySelectorAll(".tab-carreira-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-carreira-btn").forEach(b => b.classList.remove("ativo"));
    document.querySelectorAll(".tab-carreira-content").forEach(c => c.classList.remove("ativo"));
    btn.classList.add("ativo");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("ativo");
    if (ABAS_COM_ASSINATURA.has(btn.dataset.tab) && !temAssinaturaCarreira) return;
    if (btn.dataset.tab === "historico") carregarHistorico();
    if (btn.dataset.tab === "estatisticas") carregarEstatisticas();
    if (btn.dataset.tab === "compartilhar") gerarImagemStory();
  });
});

function bannerProPara(tipoPerfil) {
  return tipoPerfil === "mestre"
    ? { imagem: "img/banner-plano-mestre-pro.jpg", nome: "Mestre PRO" }
    : { imagem: "img/banner-plano-atleta-pro.jpg", nome: "Atleta PRO" };
}

function aplicarBloqueioPro(tipoPerfil) {
  const { imagem, nome } = bannerProPara(tipoPerfil);
  document.querySelectorAll(".bloqueio-pro").forEach(elBloqueio => {
    elBloqueio.innerHTML = `
      <div class="card-carreira" style="text-align:center; max-width:480px; margin:0 auto;">
        <img src="${imagem}" alt="Plano ${nome}" style="width:100%; border-radius:10px; margin-bottom:12px;">
        <p style="color:#7c8894; font-size:0.9rem;">
          Essa área é exclusiva de quem assina o <strong>Plano ${nome}</strong>.
        </p>
        <a href="/assinatura"><button type="button">Assinar ${nome}</button></a>
      </div>
    `;
    elBloqueio.style.display = "block";
    const conteudo = elBloqueio.nextElementSibling;
    if (conteudo && conteudo.classList.contains("conteudo-pro")) conteudo.style.display = "none";
  });
}

async function checarSessaoCarreira() {
  try {
    const resp = await fetch("/api/sessao");
    const dados = await resp.json();
    temAssinaturaCarreira = !!(dados.assinatura && dados.assinatura.tem_acesso);

    const elCardMestre = document.getElementById("card-meu-mestre");
    if (elCardMestre) elCardMestre.style.display = dados.mestre ? "none" : "";

    if (!temAssinaturaCarreira) aplicarBloqueioPro(dados.tipo_perfil);
  } catch (err) {
    // sessão não carregou — segue sem bloquear nem esconder nada, os
    // próprios endpoints continuam protegidos no servidor de qualquer forma
  }
}

function mostrarStatus(elId, texto, ehErro = false) {
  const el = document.getElementById(elId);
  el.textContent = texto;
  el.className = "status-importacao" + (ehErro ? " erro" : "");
}

// ---------- Perfil ----------
function atualizarFotoPerfilUI(fotoUrl) {
  const elPreview = document.getElementById("p_foto_preview");
  const elPlaceholder = document.getElementById("p_foto_placeholder");
  const elBtnRemover = document.getElementById("btn-remover-foto");
  if (fotoUrl) {
    elPreview.src = fotoUrl;
    elPreview.style.display = "block";
    elPlaceholder.style.display = "none";
    elBtnRemover.style.display = "inline-block";
  } else {
    elPreview.style.display = "none";
    elPlaceholder.style.display = "flex";
    elBtnRemover.style.display = "none";
  }
}

async function carregarPerfil() {
  try {
    const resp = await fetchAutenticado("/api/carreira/perfil");
    const p = await resp.json();
    document.getElementById("p_nome").value = p.nome || "";
    document.getElementById("p_faixa").value = p.faixa || "Branca";
    document.getElementById("p_grau").value = p.grau || "0";
    document.getElementById("p_categoria").value = p.categoria || "";
    document.getElementById("p_academia").value = p.academia || "";
    document.getElementById("p_inicio").value = p.inicio || "";
    atualizarFotoPerfilUI(p.foto_url);
    atualizarLembretePerfil(p);
  } catch (err) {
    // segue com os campos vazios
  }
}

document.getElementById("p_foto_input").addEventListener("change", async (ev) => {
  const arquivo = ev.target.files[0];
  if (!arquivo) return;
  mostrarStatus("status-foto-perfil", "Enviando foto...");
  const formData = new FormData();
  formData.append("foto", arquivo);
  try {
    const resp = await fetchAutenticado("/api/carreira/foto", { method: "POST", body: formData });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui enviar a foto");
    atualizarFotoPerfilUI(dados.foto_url);
    mostrarStatus("status-foto-perfil", "Foto atualizada!");
  } catch (err) {
    mostrarStatus("status-foto-perfil", `Erro: ${err.message}`, true);
  } finally {
    ev.target.value = "";
  }
});

document.getElementById("btn-remover-foto").addEventListener("click", async () => {
  if (!confirm("Remover a foto do perfil?")) return;
  try {
    const resp = await fetchAutenticado("/api/carreira/foto", { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover a foto");
    atualizarFotoPerfilUI(null);
    mostrarStatus("status-foto-perfil", "Foto removida.");
  } catch (err) {
    mostrarStatus("status-foto-perfil", `Erro: ${err.message}`, true);
  }
});

// Aviso fixo (visível em qualquer aba) enquanto faltar nome, faixa ou
// academia — sem esses três preenchidos, o vínculo com Mestre/Alunos e o
// resumo para o Stories saem incompletos. Nome de usuário do Mestre fica de
// fora de propósito: o aluno pode não ter o Mestre cadastrado ainda.
function atualizarLembretePerfil(perfil) {
  const elAviso = document.getElementById("lembrete-perfil");
  const faltando = [];
  if (!(perfil.nome || "").trim()) faltando.push("nome completo");
  if (!(perfil.faixa || "").trim()) faltando.push("faixa");
  if (!(perfil.academia || "").trim()) faltando.push("academia");

  if (!faltando.length) {
    elAviso.style.display = "none";
    return;
  }
  document.getElementById("lembrete-perfil-texto").textContent =
    `Falta preencher: ${faltando.join(", ")}. Isso é essencial para o vínculo com Mestre/Alunos funcionar direito.`;
  elAviso.style.display = "flex";
}

document.querySelector('[data-tab-link="perfil"]').addEventListener("click", () => {
  document.querySelector('.tab-carreira-btn[data-tab="perfil"]').click();
});

document.getElementById("form-perfil").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const dados = {
    nome: document.getElementById("p_nome").value,
    faixa: document.getElementById("p_faixa").value,
    grau: document.getElementById("p_grau").value,
    categoria: document.getElementById("p_categoria").value,
    academia: document.getElementById("p_academia").value,
    inicio: document.getElementById("p_inicio").value,
  };
  try {
    const resp = await fetchAutenticado("/api/carreira/perfil", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(dados),
    });
    if (!resp.ok) throw new Error("não consegui salvar o perfil");
    mostrarStatus("status-perfil", "Perfil salvo! 🥋");
    atualizarLembretePerfil(dados);
  } catch (err) {
    mostrarStatus("status-perfil", `Erro: ${err.message}`, true);
  }
});

// ---------- Nome de usuário ----------
async function carregarNomeUsuario() {
  try {
    const resp = await fetchAutenticado("/api/conta/nome-usuario");
    const dados = await resp.json();
    document.getElementById("nome_usuario").value = dados.nome_usuario || "";
  } catch (err) {
    // segue com o campo vazio
  }
}

document.getElementById("form-nome-usuario").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const nomeUsuario = document.getElementById("nome_usuario").value;
  try {
    const resp = await fetchAutenticado("/api/conta/nome-usuario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome_usuario: nomeUsuario }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui salvar");
    mostrarStatus("status-nome-usuario", "Nome de usuário salvo!");
  } catch (err) {
    mostrarStatus("status-nome-usuario", `Erro: ${err.message}`, true);
  }
});

// ---------- Meu(s) Mestre(s) ----------
async function carregarMestres() {
  const el = document.getElementById("lista-mestres");
  try {
    const resp = await fetchAutenticado("/api/carreira/meu-mestre");
    const mestres = await resp.json();
    if (!mestres.length) {
      el.innerHTML = "";
      return;
    }
    el.innerHTML = mestres.map(m => `
      <div class="cartao-alerta" style="margin-bottom: 8px;">
        <div class="cartao-alerta-topo">
          <div>
            <h3 style="font-size: 0.95rem;">${m.nome || "(sem nome)"}</h3>
            ${m.academia ? `<div class="cartao-alerta-federacao">${m.academia}</div>` : ""}
          </div>
          <button type="button" class="btn-remover" data-id="${m.usuario_id}">Remover</button>
        </div>
      </div>
    `).join("");
    el.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => removerMestre(Number(btn.dataset.id)));
    });
  } catch (err) {
    mostrarStatus("status-mestre", `Erro: ${err.message}`, true);
  }
}

document.getElementById("form-add-mestre").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const elInput = document.getElementById("mestre_nome_usuario");
  try {
    const resp = await fetchAutenticado("/api/carreira/meu-mestre", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome_usuario: elInput.value }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui adicionar");
    mostrarStatus("status-mestre", "Mestre adicionado!");
    elInput.value = "";
    carregarMestres();
  } catch (err) {
    mostrarStatus("status-mestre", `Erro: ${err.message}`, true);
  }
});

async function removerMestre(mestreId) {
  try {
    const resp = await fetchAutenticado(`/api/carreira/meu-mestre/${mestreId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    carregarMestres();
  } catch (err) {
    mostrarStatus("status-mestre", `Erro: ${err.message}`, true);
  }
}

// ---------- Registrar ----------
const lutasContainer = document.getElementById("lutas-container");
const templateLutaRow = document.getElementById("template-luta-row");

function addLutaRow(luta) {
  const frag = templateLutaRow.content.cloneNode(true);
  const row = frag.querySelector(".luta-row");
  if (luta) {
    row.querySelector(".luta-adversario").value = luta.adversario || "";
    row.querySelector(".luta-resultado").value = luta.resultado || "vitoria";
    row.querySelector(".luta-metodo").value = luta.metodo || "pontos";
  }
  row.querySelector(".btn-remove-luta").addEventListener("click", () => row.remove());
  lutasContainer.appendChild(row);
}

document.getElementById("btn-add-luta").addEventListener("click", () => addLutaRow());

function resetFormCompeticao() {
  document.getElementById("form-competicao").reset();
  document.getElementById("e_editing_id").value = "";
  document.getElementById("e_pais").value = "Brasil";
  lutasContainer.innerHTML = "";
  addLutaRow();
  document.getElementById("btn-salvar-competicao").textContent = "Salvar Registro";
  document.getElementById("btn-cancelar-edicao").classList.add("hidden");
  document.getElementById("e_data").valueAsDate = new Date();
}

document.getElementById("btn-cancelar-edicao").addEventListener("click", resetFormCompeticao);

document.getElementById("form-competicao").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const editingId = document.getElementById("e_editing_id").value;
  const lutas = [...lutasContainer.querySelectorAll(".luta-row")].map(row => ({
    adversario: row.querySelector(".luta-adversario").value,
    resultado: row.querySelector(".luta-resultado").value,
    metodo: row.querySelector(".luta-metodo").value,
  }));
  const dados = {
    data: document.getElementById("e_data").value,
    campeonato: document.getElementById("e_campeonato").value,
    categoria: document.getElementById("e_categoria").value,
    pais: document.getElementById("e_pais").value || "Brasil",
    medalha: document.getElementById("e_medalha").value || null,
    lutas,
  };

  try {
    const resp = editingId
      ? await fetchAutenticado(`/api/carreira/competicoes/${editingId}`, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados),
        })
      : await fetchAutenticado("/api/carreira/competicoes", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(dados),
        });
    const resultado = await resp.json();
    if (!resp.ok) throw new Error(resultado.erro || "não consegui salvar");

    mostrarStatus("status-competicao", editingId ? "Competição atualizada! 🥋" : "Competição salva! 🥋");
    resetFormCompeticao();
    carregarHistorico();
  } catch (err) {
    mostrarStatus("status-competicao", `Erro: ${err.message}`, true);
  }
});

function irParaAbaRegistrar(competicao) {
  document.getElementById("e_editing_id").value = competicao.id;
  document.getElementById("e_data").value = competicao.data || "";
  document.getElementById("e_campeonato").value = competicao.campeonato || "";
  document.getElementById("e_categoria").value = competicao.categoria || "";
  document.getElementById("e_pais").value = competicao.pais || "Brasil";
  document.getElementById("e_medalha").value = competicao.medalha || "";
  lutasContainer.innerHTML = "";
  (competicao.lutas || []).forEach(l => addLutaRow(l));
  if (!competicao.lutas || competicao.lutas.length === 0) addLutaRow();

  document.getElementById("btn-salvar-competicao").textContent = "Atualizar Registro";
  document.getElementById("btn-cancelar-edicao").classList.remove("hidden");

  document.querySelectorAll(".tab-carreira-btn").forEach(b => b.classList.remove("ativo"));
  document.querySelectorAll(".tab-carreira-content").forEach(c => c.classList.remove("ativo"));
  document.querySelector('.tab-carreira-btn[data-tab="registrar"]').classList.add("ativo");
  document.getElementById("tab-registrar").classList.add("ativo");
}

async function removerCompeticao(id) {
  if (!confirm("Excluir esta competição (e todas as lutas dela)?")) return;
  try {
    const resp = await fetchAutenticado(`/api/carreira/competicoes/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    carregarHistorico();
  } catch (err) {
    mostrarStatus("status-competicao", `Erro ao remover: ${err.message}`, true);
  }
}

// ---------- Cards ----------
const RESULTADO_LABEL = { vitoria: "Vitória", derrota: "Derrota", empate: "Empate" };
const METODO_LABEL = { pontos: "Pontos", finalizacao: "Finalização", wo: "W.O.", desclassificacao: "Desclassificação", medica: "Médica" };
const MEDALHA_LABEL = { ouro: "🥇 Ouro", prata: "🥈 Prata", bronze: "🥉 Bronze" };

function formatarData(data) {
  if (!data) return "";
  const iso = data.includes("T") ? data : data + "T00:00:00";
  return new Date(iso).toLocaleDateString("pt-BR");
}

function cardCompeticao(c, competicoesPorId) {
  let tags = "";
  if (c.medalha) tags += `<span class="tag-carreira medalha-${c.medalha}">${MEDALHA_LABEL[c.medalha]}</span>`;
  if (c.pais && c.pais !== "Brasil") tags += `<span class="tag-carreira pais">🌎 ${c.pais}</span>`;
  const metaPartes = [formatarData(c.data)];
  if (c.categoria) metaPartes.push(c.categoria);
  const lutasHtml = (c.lutas || []).map(l => `
    <div class="luta-item">
      <span class="tag-carreira ${l.resultado}">${RESULTADO_LABEL[l.resultado]}</span>
      ${l.adversario ? "vs " + l.adversario : ""}${l.metodo ? " · " + METODO_LABEL[l.metodo] : ""}
    </div>`).join("");
  return `
    <div class="cartao-alerta">
      <div class="cartao-alerta-topo">
        <div>
          <h3>${tags}${c.campeonato || "Competição"}</h3>
          <div class="cartao-alerta-federacao">${metaPartes.join(" · ")}</div>
        </div>
        <div style="display:flex; gap: 6px; flex-shrink: 0;">
          <button type="button" class="btn-secundario btn-editar" data-id="${c.id}">Editar</button>
          <button type="button" class="btn-remover" data-id="${c.id}">Remover</button>
        </div>
      </div>
      <div class="lutas-list">${lutasHtml}</div>
    </div>`;
}

function ligarBotoesCard(container, competicoes) {
  container.querySelectorAll(".btn-editar").forEach(btn => {
    btn.addEventListener("click", () => {
      const c = competicoes.find(comp => comp.id === Number(btn.dataset.id));
      if (c) irParaAbaRegistrar(c);
    });
  });
  container.querySelectorAll(".btn-remover").forEach(btn => {
    btn.addEventListener("click", () => removerCompeticao(Number(btn.dataset.id)));
  });
}

// ---------- Histórico ----------
async function carregarHistorico() {
  const el = document.getElementById("lista-historico");
  try {
    const resp = await fetchAutenticado("/api/carreira/competicoes");
    const competicoes = await resp.json();
    if (!competicoes.length) {
      el.innerHTML = '<p style="color:#7c8894;">Nenhum registro ainda. Vai lá registrar sua primeira competição!</p>';
      return;
    }
    el.innerHTML = competicoes.map(c => cardCompeticao(c)).join("");
    ligarBotoesCard(el, competicoes);
  } catch (err) {
    el.innerHTML = `<p class="erro">Erro ao carregar: ${err.message}</p>`;
  }
}

// ---------- Pesquisa ----------
document.getElementById("form-pesquisa").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const params = new URLSearchParams({
    campeonato: document.getElementById("s_campeonato").value,
    adversario: document.getElementById("s_adversario").value,
    de: document.getElementById("s_de").value,
    ate: document.getElementById("s_ate").value,
  });
  const elContagem = document.getElementById("contagem-pesquisa");
  const elLista = document.getElementById("lista-pesquisa");
  try {
    const resp = await fetchAutenticado(`/api/carreira/competicoes?${params}`);
    const competicoes = await resp.json();
    elContagem.textContent = `${competicoes.length} resultado(s)`;
    elLista.innerHTML = competicoes.length
      ? competicoes.map(c => cardCompeticao(c)).join("")
      : '<p style="color:#7c8894;">Nenhuma competição encontrada com esses filtros.</p>';
    ligarBotoesCard(elLista, competicoes);
  } catch (err) {
    elContagem.textContent = "";
    elLista.innerHTML = `<p class="erro">Erro: ${err.message}</p>`;
  }
});

document.getElementById("btn-limpar-pesquisa").addEventListener("click", () => {
  document.getElementById("form-pesquisa").reset();
  document.getElementById("contagem-pesquisa").textContent = "";
  document.getElementById("lista-pesquisa").innerHTML = "";
});

// ---------- Estatísticas ----------
async function carregarEstatisticas() {
  try {
    const resp = await fetchAutenticado("/api/carreira/estatisticas");
    const s = await resp.json();

    const stats = [
      { label: "Competições", value: s.competicoes },
      { label: "Lutas", value: s.lutas },
      { label: "Vitórias", value: s.vitorias },
      { label: "Derrotas", value: s.derrotas },
      { label: "Empates", value: s.empates },
      { label: "Taxa de vitória", value: s.taxa_vitoria + "%" },
      { label: "Sequência atual", value: s.sequencia_atual },
      { label: "Melhor sequência", value: s.melhor_sequencia },
      { label: "Finalizações", value: s.finalizacoes },
      { label: "Vitórias por pontos", value: s.vitorias_pontos },
      { label: "Campeonatos diferentes", value: s.campeonatos_diferentes },
      { label: "Países diferentes", value: s.paises_diferentes },
      { label: "🥇 Ouros", value: s.ouros },
      { label: "🥈 Pratas", value: s.pratas },
      { label: "🥉 Bronzes", value: s.bronzes },
    ];
    document.getElementById("grade-estatisticas").innerHTML = stats.map(item => `
      <div class="stat-box">
        <div class="stat-value">${item.value}</div>
        <div class="stat-label">${item.label}</div>
      </div>`).join("");

    desenharGrafico(s.grafico || []);
  } catch (err) {
    document.getElementById("grade-estatisticas").innerHTML = `<p class="erro">Erro: ${err.message}</p>`;
  }
}

function desenharGrafico(pontos) {
  const svg = document.getElementById("grafico-evolucao");
  const W = 600, H = 240, PAD = 30;
  if (!pontos.length) {
    svg.innerHTML = `<text x="${W / 2}" y="${H / 2}" text-anchor="middle" fill="#888" font-size="14">Sem competições registradas ainda</text>`;
    return;
  }

  const maxY = Math.max(...pontos.map(p => p.vitorias_acumuladas), 1);
  const maxX = Math.max(pontos.length - 1, 1);
  const escalaX = i => PAD + (i / maxX) * (W - 2 * PAD);
  const escalaY = y => H - PAD - (y / maxY) * (H - 2 * PAD);

  const pathD = pontos.map((p, i) => `${i === 0 ? "M" : "L"} ${escalaX(i)} ${escalaY(p.vitorias_acumuladas)}`).join(" ");
  const cores = { vitoria: "#4caf50", derrota: "#ef5350", empate: "#f9a825" };
  const pontosSvg = pontos.map((p, i) =>
    `<circle cx="${escalaX(i)}" cy="${escalaY(p.vitorias_acumuladas)}" r="4" fill="${cores[p.resultado]}" />`
  ).join("");

  svg.innerHTML = `
    <line x1="${PAD}" y1="${H - PAD}" x2="${W - PAD}" y2="${H - PAD}" stroke="#888" stroke-width="1"/>
    <line x1="${PAD}" y1="${PAD}" x2="${PAD}" y2="${H - PAD}" stroke="#888" stroke-width="1"/>
    <path d="${pathD}" fill="none" stroke="#4caf50" stroke-width="2"/>
    ${pontosSvg}
    <text x="${PAD}" y="${H - 8}" font-size="11" fill="#888">Início</text>
    <text x="${W - PAD}" y="${H - 8}" font-size="11" fill="#888" text-anchor="end">Hoje</text>
    <text x="${PAD - 6}" y="${PAD + 4}" font-size="11" fill="#888" text-anchor="end">${maxY}</text>
  `;
}

// ---------- Compartilhar (imagem para o Stories) ----------
const CORES_FAIXA = {
  "branca": "#f4f6f8", "cinza-branca": "#c7ccd1", "cinza": "#9aa1a8", "cinza-preta": "#5c636b",
  "amarela-branca": "#fff6c9", "amarela": "#f4d90c", "amarela-preta": "#c9b400",
  "laranja-branca": "#ffd9b3", "laranja": "#f28c28", "laranja-preta": "#b8611b",
  "verde-branca": "#c9f2d0", "verde": "#2e9e44", "verde-preta": "#1d6b2c",
  "azul": "#1e6091", "roxa": "#5b2e91", "marrom": "#5a3b23", "preta": "#111418",
};

function corDaFaixa(faixa) {
  return CORES_FAIXA[(faixa || "").toLowerCase()] || "#1e6091";
}

let ultimoBlobStory = null;

function carregarImagem(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function cartaoComGlow(ctx, x, y, w, h, r, corBorda) {
  ctx.fillStyle = "rgba(255,255,255,0.05)";
  roundRect(ctx, x, y, w, h, r);
  ctx.fill();

  ctx.save();
  ctx.shadowColor = corBorda;
  ctx.shadowBlur = 16;
  ctx.strokeStyle = corBorda;
  ctx.lineWidth = 2;
  roundRect(ctx, x, y, w, h, r);
  ctx.stroke();
  ctx.restore();
}

async function gerarImagemStory() {
  const canvas = document.getElementById("canvas-story");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const CIANO = "#7fd4ff";
  const CINZA_AZULADO = "#b7cbdc";

  mostrarStatus("status-story", "Gerando imagem...");

  // Usa o que já está no formulário de Perfil (carregado no início da
  // página) em vez de buscar de novo — evita mostrar o nome de fallback
  // quando o campo já está preenchido na tela mas ainda não foi salvo.
  const perfil = {
    nome: document.getElementById("p_nome").value,
    faixa: document.getElementById("p_faixa").value,
    grau: document.getElementById("p_grau").value,
    academia: document.getElementById("p_academia").value,
  };

  let stats = {};
  try {
    const respStats = await fetchAutenticado("/api/carreira/estatisticas");
    stats = await respStats.json();
  } catch (err) {
    mostrarStatus("status-story", `Erro ao carregar dados: ${err.message}`, true);
    return;
  }

  // Fundo em gradiente, com um brilho difuso atrás do cabeçalho pra dar
  // profundidade (parecido com o fundo "tech" do template de referência).
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, "#0b3d63");
  grad.addColorStop(1, "#050810");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  const brilho = ctx.createRadialGradient(W / 2, 260, 40, W / 2, 260, 520);
  brilho.addColorStop(0, "rgba(127, 212, 255, 0.22)");
  brilho.addColorStop(1, "rgba(127, 212, 255, 0)");
  ctx.fillStyle = brilho;
  ctx.fillRect(0, 0, W, H);

  ctx.textAlign = "center";

  // Banner do site, no topo
  let yBanner = 70;
  let yAposBanner = 280;
  try {
    const banner = await carregarImagem("img/banner.jpg");
    const larguraBanner = 580;
    const alturaBanner = larguraBanner * (banner.height / banner.width);
    ctx.save();
    ctx.shadowColor = "rgba(127, 212, 255, 0.5)";
    ctx.shadowBlur = 30;
    roundRect(ctx, W / 2 - larguraBanner / 2, yBanner, larguraBanner, alturaBanner, 14);
    ctx.clip();
    ctx.drawImage(banner, W / 2 - larguraBanner / 2, yBanner, larguraBanner, alturaBanner);
    ctx.restore();
    yAposBanner = yBanner + alturaBanner + 32;
  } catch (err) {
    // segue sem o banner se não conseguir carregar
  }

  // Foto de perfil (redonda), logo abaixo do banner — usa a mesma foto já
  // exibida no formulário de Perfil (evita buscar de novo, mesma lógica do
  // resto dos dados desta função). Sem foto cadastrada, cai num círculo com
  // o emoji padrão, pra não deixar um espaço vazio ali.
  const elFotoPreview = document.getElementById("p_foto_preview");
  const fotoUrl = elFotoPreview.style.display !== "none" ? elFotoPreview.src : null;

  const raioFoto = 68;
  const cxFoto = W / 2;
  const cyFoto = yAposBanner + raioFoto;

  ctx.save();
  ctx.beginPath();
  ctx.arc(cxFoto, cyFoto, raioFoto + 4, 0, Math.PI * 2);
  ctx.shadowColor = "rgba(127, 212, 255, 0.6)";
  ctx.shadowBlur = 26;
  ctx.fillStyle = "rgba(127, 212, 255, 0.15)";
  ctx.fill();
  ctx.restore();

  ctx.save();
  ctx.beginPath();
  ctx.arc(cxFoto, cyFoto, raioFoto, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();
  let fotoCarregada = null;
  if (fotoUrl) {
    try {
      fotoCarregada = await carregarImagem(fotoUrl);
    } catch (err) {
      fotoCarregada = null;
    }
  }
  if (fotoCarregada) {
    ctx.drawImage(fotoCarregada, cxFoto - raioFoto, cyFoto - raioFoto, raioFoto * 2, raioFoto * 2);
  } else {
    ctx.fillStyle = "#12314f";
    ctx.fillRect(cxFoto - raioFoto, cyFoto - raioFoto, raioFoto * 2, raioFoto * 2);
    ctx.font = "60px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText("🥋", cxFoto, cyFoto + 21);
  }
  ctx.restore();

  ctx.beginPath();
  ctx.arc(cxFoto, cyFoto, raioFoto, 0, Math.PI * 2);
  ctx.strokeStyle = CIANO;
  ctx.lineWidth = 5;
  ctx.stroke();

  yAposBanner = cyFoto + raioFoto + 36;

  // "RESUMO DE CARREIRA" com dois tracinhos decorativos ao lado
  ctx.font = "26px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "4px";
  ctx.fillStyle = CINZA_AZULADO;
  const rotuloResumo = "RESUMO DE CARREIRA";
  const larguraResumo = ctx.measureText(rotuloResumo).width;
  ctx.fillText(rotuloResumo, W / 2, yAposBanner);
  ctx.letterSpacing = "0px";
  ctx.strokeStyle = "rgba(127, 212, 255, 0.7)";
  ctx.lineWidth = 2;
  const xResumoEsq = W / 2 - larguraResumo / 2 - 40;
  const xResumoDir = W / 2 + larguraResumo / 2 + 40;
  ctx.beginPath();
  ctx.moveTo(xResumoEsq - 26, yAposBanner - 8);
  ctx.lineTo(xResumoEsq, yAposBanner - 8);
  ctx.moveTo(xResumoDir, yAposBanner - 8);
  ctx.lineTo(xResumoDir + 26, yAposBanner - 8);
  ctx.stroke();

  // Nome do atleta
  const nome = perfil.nome || "Atleta Radar BJJ";
  let tamanhoNome = 68;
  ctx.font = `bold ${tamanhoNome}px -apple-system, Arial, sans-serif`;
  while (ctx.measureText(nome).width > W - 120 && tamanhoNome > 36) {
    tamanhoNome -= 4;
    ctx.font = `bold ${tamanhoNome}px -apple-system, Arial, sans-serif`;
  }
  ctx.fillStyle = "#ffffff";
  const yNome = yAposBanner + 70;
  ctx.fillText(nome, W / 2, yNome);

  // Faixa (badge)
  const faixa = perfil.faixa || "Branca";
  const grau = Number(perfil.grau || 0);
  const faixaTexto = `Faixa ${faixa}${grau > 0 ? " · " + grau + "º grau" : ""}`;
  ctx.font = "bold 30px -apple-system, Arial, sans-serif";
  const larguraBadge = ctx.measureText(faixaTexto).width + 70;
  const xBadge = W / 2 - larguraBadge / 2;
  const yBadge = yNome + 42;
  ctx.fillStyle = corDaFaixa(faixa);
  roundRect(ctx, xBadge, yBadge, larguraBadge, 58, 29);
  ctx.fill();
  ctx.fillStyle = ["preta", "azul", "roxa", "marrom", "verde", "verde-preta", "cinza-preta", "laranja-preta", "amarela-preta"].includes(faixa.toLowerCase()) ? "#ffffff" : "#1c2733";
  ctx.fillText(faixaTexto, W / 2, yBadge + 39);

  let yAcademia = yBadge + 58 + 40;
  if (perfil.academia) {
    ctx.font = "30px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CINZA_AZULADO;
    ctx.fillText(`🦁 ${perfil.academia}`, W / 2, yAcademia);
  } else {
    yAcademia -= 30;
  }

  // Grade de estatísticas — 3 linhas x 2 colunas, ícone + número + rótulo
  // lado a lado dentro de cada cartão com borda brilhante.
  const statsPrincipais = [
    { icone: "🏆", valor: stats.competicoes || 0, label: "COMPETIÇÕES" },
    { icone: "🎖️", valor: stats.vitorias || 0, label: "VITÓRIAS" },
    { icone: "🎯", valor: (stats.taxa_vitoria || 0) + "%", label: "TAXA DE VITÓRIA" },
    { icone: "📈", valor: stats.sequencia_atual || 0, label: "SEQUÊNCIA ATUAL" },
    { icone: "⚡", valor: stats.melhor_sequencia || 0, label: "MELHOR SEQUÊNCIA" },
    { icone: "🥋", valor: stats.finalizacoes || 0, label: "FINALIZAÇÕES" },
  ];

  const margem = 60;
  const gapGrid = 18;
  const colW = (W - margem * 2 - gapGrid) / 2;
  const linhaAltura = 165;
  const gridTopo = yAcademia + 42;

  statsPrincipais.forEach((item, i) => {
    const col = i % 2;
    const linha = Math.floor(i / 2);
    const x = margem + col * (colW + gapGrid);
    const y = gridTopo + linha * (linhaAltura + gapGrid);

    cartaoComGlow(ctx, x, y, colW, linhaAltura, 22, "rgba(127, 212, 255, 0.4)");

    const cy = y + linhaAltura / 2;
    ctx.textAlign = "center";
    ctx.font = "56px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(item.icone, x + 90, cy + 20);

    ctx.textAlign = "left";
    ctx.font = "bold 52px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CIANO;
    ctx.fillText(String(item.valor), x + 155, cy - 6);

    ctx.font = "21px -apple-system, Arial, sans-serif";
    ctx.letterSpacing = "1px";
    ctx.fillStyle = CINZA_AZULADO;
    ctx.fillText(item.label, x + 155, cy + 34);
    ctx.letterSpacing = "0px";
  });
  ctx.textAlign = "center";

  const gridFim = gridTopo + 3 * linhaAltura + 2 * gapGrid;

  // Pódio — barras com altura proporcional ao lugar (ouro no centro, mais
  // alta), medalha fixa no topo do painel e a contagem dentro de cada barra.
  const painelY = gridFim + 30;
  const painelAltura = 330;
  cartaoComGlow(ctx, margem, painelY, W - margem * 2, painelAltura, 24, "rgba(127, 212, 255, 0.3)");

  const medalhas = [
    { icone: "🥈", valor: stats.pratas || 0, alturaBarra: 95, cor: "rgba(200, 210, 220, 0.35)" },
    { icone: "🥇", valor: stats.ouros || 0, alturaBarra: 148, cor: "rgba(255, 215, 90, 0.4)" },
    { icone: "🥉", valor: stats.bronzes || 0, alturaBarra: 70, cor: "rgba(205, 140, 90, 0.4)" },
  ];
  const larguraBarra = 200;
  const gapBarra = 40;
  const larguraTotalBarras = larguraBarra * 3 + gapBarra * 2;
  const xInicioBarras = margem + (W - margem * 2 - larguraTotalBarras) / 2;
  const baseBarras = painelY + painelAltura - 43;
  const yMedalha = painelY + 87;

  medalhas.forEach((m, i) => {
    const x = xInicioBarras + i * (larguraBarra + gapBarra);
    const yBarra = baseBarras - m.alturaBarra;

    ctx.fillStyle = m.cor;
    roundRect(ctx, x, yBarra, larguraBarra, m.alturaBarra, 14);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,0.5)";
    ctx.lineWidth = 1.5;
    roundRect(ctx, x, yBarra, larguraBarra, m.alturaBarra, 14);
    ctx.stroke();

    ctx.font = "58px -apple-system, Arial, sans-serif";
    ctx.fillText(m.icone, x + larguraBarra / 2, yMedalha);

    ctx.font = "bold 48px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(String(m.valor), x + larguraBarra / 2, yBarra + m.alturaBarra / 2 + 17);
  });

  // Rodapé — link em destaque, com fundo para chamar atenção no Stories
  const urlSite = "www.radarbjj.com";
  ctx.font = "bold 40px -apple-system, Arial, sans-serif";
  const larguraUrl = ctx.measureText(urlSite).width + 90;
  const yUrl = painelY + painelAltura + 65;
  ctx.fillStyle = "rgba(127, 212, 255, 0.15)";
  roundRect(ctx, W / 2 - larguraUrl / 2, yUrl - 44, larguraUrl, 64, 32);
  ctx.fill();
  ctx.strokeStyle = "rgba(127, 212, 255, 0.5)";
  ctx.lineWidth = 1.5;
  roundRect(ctx, W / 2 - larguraUrl / 2, yUrl - 44, larguraUrl, 64, 32);
  ctx.stroke();
  ctx.fillStyle = CIANO;
  ctx.fillText(`🌐 ${urlSite}`, W / 2, yUrl);

  canvas.toBlob(blob => {
    ultimoBlobStory = blob;
    mostrarStatus("status-story", "Imagem pronta! 🥋");
    const btnCompartilhar = document.getElementById("btn-compartilhar-story");
    if (navigator.canShare && blob && navigator.canShare({ files: [new File([blob], "story.png", { type: "image/png" })] })) {
      btnCompartilhar.classList.remove("hidden");
    } else {
      btnCompartilhar.classList.add("hidden");
    }
  }, "image/png");
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

document.getElementById("btn-baixar-story").addEventListener("click", () => {
  if (!ultimoBlobStory) return;
  const url = URL.createObjectURL(ultimoBlobStory);
  const a = document.createElement("a");
  a.href = url;
  a.download = "radar-bjj-carreira.png";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("btn-compartilhar-story").addEventListener("click", async () => {
  if (!ultimoBlobStory) return;
  try {
    await navigator.share({
      files: [new File([ultimoBlobStory], "radar-bjj-carreira.png", { type: "image/png" })],
      title: "Minha carreira no Radar BJJ",
    });
  } catch (err) {
    // usuário cancelou o compartilhamento — sem problema
  }
});

// ---------- Init ----------
addLutaRow();
document.getElementById("e_data").valueAsDate = new Date();
carregarPerfil();
carregarNomeUsuario();
carregarMestres();
checarSessaoCarreira();
