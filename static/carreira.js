// ---------- Abas internas ----------
// Todas as abas daqui (Registrar, Histórico, Pesquisa, Estatísticas,
// Compartilhar) exigem assinatura; sem ela, ficam bloqueadas com o banner
// do Plano PRO correspondente em vez do conteúdo real (ver
// aplicarBloqueioPro). O Perfil em si (nome, foto, faixa, nome de usuário,
// vínculo com Mestre) é liberado pro Free e virou página própria (ver
// static/perfil.js) — não mora mais aqui.
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
        <p style="color:#55606b; font-size:0.9rem;">
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
    if (!temAssinaturaCarreira) aplicarBloqueioPro(dados.tipo_perfil);
  } catch (err) {
    // sessão não carregou — segue sem bloquear nada, os próprios endpoints
    // continuam protegidos no servidor de qualquer forma
  }
}

function mostrarStatus(elId, texto, ehErro = false) {
  const el = document.getElementById(elId);
  el.textContent = texto;
  el.className = "status-importacao" + (ehErro ? " erro" : "");
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
      el.innerHTML = '<p style="color:#55606b;">Nenhum registro ainda. Vai lá registrar sua primeira competição!</p>';
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
      : '<p style="color:#55606b;">Nenhuma competição encontrada com esses filtros.</p>';
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

async function gerarImagemStory() {
  const canvas = document.getElementById("canvas-story");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const CIANO = "#7fd4ff";
  const CINZA_AZULADO = "#b7cbdc";

  mostrarStatus("status-story", "Gerando imagem...");

  // O formulário de Perfil virou página própria (ver static/perfil.js) —
  // não dá mais pra ler os campos direto da tela, busca via API.
  let perfil = { nome: "", faixa: "Branca", grau: "0", academia: "", nomeUsuario: "" };
  try {
    const [respPerfil, respNomeUsuario] = await Promise.all([
      fetchAutenticado("/api/carreira/perfil"),
      fetchAutenticado("/api/conta/nome-usuario"),
    ]);
    const p = await respPerfil.json();
    const nu = await respNomeUsuario.json();
    perfil = {
      nome: p.nome || "",
      faixa: p.faixa || "Branca",
      grau: p.grau || "0",
      academia: p.academia || "",
      nomeUsuario: nu.nome_usuario || "",
      fotoUrl: p.foto_url || null,
    };
  } catch (err) {
    // segue com os valores padrão se não conseguir buscar
  }

  let stats = {};
  try {
    const respStats = await fetchAutenticado("/api/carreira/estatisticas");
    stats = await respStats.json();
  } catch (err) {
    mostrarStatus("status-story", `Erro ao carregar dados: ${err.message}`, true);
    return;
  }

  // Fundo escuro azulado + tarjas de canto — mesma identidade visual do
  // Story de Minha Agenda (ver static/agenda.js), pra manter as duas
  // imagens geradas pelo site com a mesma família visual.
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, "#0d1d33");
  grad.addColorStop(1, "#050b16");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  const brilho = ctx.createRadialGradient(W / 2, 200, 40, W / 2, 200, 480);
  brilho.addColorStop(0, "rgba(127, 212, 255, 0.14)");
  brilho.addColorStop(1, "rgba(127, 212, 255, 0)");
  ctx.fillStyle = brilho;
  ctx.fillRect(0, 0, W, H);

  desenharTarjasCanto(ctx, W, H);

  ctx.textAlign = "center";

  // Logo do site, no topo.
  let yLogoFim = 90;
  try {
    const logo = await carregarImagem("img/radar-bjj-logo-3d.png");
    const larguraLogo = 340;
    const alturaLogo = larguraLogo * (logo.height / logo.width);
    ctx.drawImage(logo, W / 2 - larguraLogo / 2, 40, larguraLogo, alturaLogo);
    yLogoFim = 40 + alturaLogo;
  } catch (err) {
    // segue sem o logo se não conseguir carregar
  }

  // Cabeçalho "MINHA CARREIRA": linha — círculo com ícone de medalha —
  // título — linha (mesmo padrão do cabeçalho de Minha Agenda; usa o
  // ícone em vez da foto aqui porque a foto de perfil já tem um destaque
  // maior e próprio logo abaixo, ver cxFoto/cyFoto).
  const yTituloCabecalho = yLogoFim + 55;
  const raioCirculoCabecalho = 40;
  ctx.font = "bold 40px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "1px";
  const tituloCabecalho = "MINHA CARREIRA";
  const larguraTituloCabecalho = ctx.measureText(tituloCabecalho).width;
  const xCirculoCabecalho = W / 2 - larguraTituloCabecalho / 2 - raioCirculoCabecalho - 22;

  ctx.fillStyle = "#0d1d33";
  ctx.beginPath();
  ctx.arc(xCirculoCabecalho, yTituloCabecalho, raioCirculoCabecalho, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = CIANO;
  ctx.lineWidth = 2.5;
  ctx.stroke();
  desenharIcone(ctx, "medalha", xCirculoCabecalho, yTituloCabecalho, 38, CIANO, 2);

  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.fillText(tituloCabecalho, xCirculoCabecalho + raioCirculoCabecalho + 22, yTituloCabecalho + 14);
  ctx.letterSpacing = "0px";

  ctx.strokeStyle = "rgba(127, 212, 255, 0.6)";
  ctx.lineWidth = 2;
  const xLinhaCabecalhoEsq = xCirculoCabecalho - raioCirculoCabecalho - 18;
  const xLinhaCabecalhoDir = xCirculoCabecalho + raioCirculoCabecalho + 22 + larguraTituloCabecalho + 18;
  ctx.beginPath();
  ctx.moveTo(60, yTituloCabecalho);
  ctx.lineTo(xLinhaCabecalhoEsq, yTituloCabecalho);
  ctx.moveTo(xLinhaCabecalhoDir, yTituloCabecalho);
  ctx.lineTo(W - 60, yTituloCabecalho);
  ctx.stroke();
  ctx.textAlign = "center";

  let yAposBanner = yTituloCabecalho + 70;

  // Foto de perfil (redonda) — já veio junto no fetch do perfil, lá em
  // cima. Sem foto cadastrada, cai num círculo com o emoji padrão, pra não
  // deixar um espaço vazio ali.
  const fotoUrl = perfil.fotoUrl;

  const raioFoto = 60;
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

  yAposBanner = cyFoto + raioFoto + 40;

  // Nome do atleta
  const nome = perfil.nome || "Atleta Radar BJJ";
  let tamanhoNome = 68;
  ctx.font = `bold ${tamanhoNome}px -apple-system, Arial, sans-serif`;
  while (ctx.measureText(nome).width > W - 120 && tamanhoNome > 36) {
    tamanhoNome -= 4;
    ctx.font = `bold ${tamanhoNome}px -apple-system, Arial, sans-serif`;
  }
  ctx.fillStyle = "#ffffff";
  const yNome = yAposBanner + 55;
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

  let yAcademia = yBadge + 58 + 28;
  if (perfil.academia) {
    ctx.font = "30px -apple-system, Arial, sans-serif";
    const larguraTextoAcademia = ctx.measureText(perfil.academia).width;
    const iconeAcademia = 28;
    const gapAcademia = 12;
    const xInicioAcademia = W / 2 - (iconeAcademia + gapAcademia + larguraTextoAcademia) / 2;
    desenharIcone(ctx, "pin", xInicioAcademia + iconeAcademia / 2, yAcademia - 10, iconeAcademia, CINZA_AZULADO, 2);
    ctx.textAlign = "left";
    ctx.fillStyle = CINZA_AZULADO;
    ctx.fillText(perfil.academia, xInicioAcademia + iconeAcademia + gapAcademia, yAcademia);
    ctx.textAlign = "center";
  } else {
    yAcademia -= 30;
  }

  // Grade de estatísticas — 3 linhas x 2 colunas, ícone + número + rótulo
  // lado a lado dentro de cada cartão com borda brilhante.
  const statsPrincipais = [
    { icone: "trofeu", valor: stats.competicoes || 0, label: "COMPETIÇÕES" },
    { icone: "luta", valor: stats.lutas || 0, label: "TOTAL DE LUTAS" },
    { icone: "medalha", valor: stats.vitorias || 0, label: "VITÓRIAS" },
    { icone: "alvo", valor: (stats.taxa_vitoria || 0) + "%", label: "TAXA DE VITÓRIA" },
    { icone: "tendencia", valor: stats.sequencia_atual || 0, label: "SEQUÊNCIA ATUAL" },
    { icone: "raio", valor: stats.melhor_sequencia || 0, label: "MELHOR SEQUÊNCIA" },
    { icone: "bandeira", valor: stats.finalizacoes || 0, label: "FINALIZAÇÕES" },
  ];

  const margem = 60;
  const gapGrid = 16;
  const colW = (W - margem * 2 - gapGrid) / 2;
  const linhaAltura = 114;
  const linhasGrid = Math.ceil(statsPrincipais.length / 2);
  const gridTopo = yAcademia + 28;

  statsPrincipais.forEach((item, i) => {
    const col = i % 2;
    const linha = Math.floor(i / 2);
    const x = margem + col * (colW + gapGrid);
    const y = gridTopo + linha * (linhaAltura + gapGrid);

    cartaoComGlow(ctx, x, y, colW, linhaAltura, 22, "rgba(127, 212, 255, 0.4)");

    const cy = y + linhaAltura / 2;
    desenharIcone(ctx, item.icone, x + 84, cy, 46, "#ffffff", 2.2);

    ctx.textAlign = "left";
    ctx.font = "bold 44px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CIANO;
    ctx.fillText(String(item.valor), x + 145, cy - 8);

    ctx.font = "19px -apple-system, Arial, sans-serif";
    ctx.letterSpacing = "1px";
    ctx.fillStyle = CINZA_AZULADO;
    ctx.fillText(item.label, x + 145, cy + 28);
    ctx.letterSpacing = "0px";
  });
  ctx.textAlign = "center";

  const gridFim = gridTopo + linhasGrid * linhaAltura + (linhasGrid - 1) * gapGrid;

  // Pódio — barras com altura proporcional ao lugar (ouro no centro, mais
  // alta), medalha fixa no topo do painel e a contagem dentro de cada barra.
  const painelY = gridFim + 24;
  const painelAltura = 260;
  cartaoComGlow(ctx, margem, painelY, W - margem * 2, painelAltura, 24, "rgba(127, 212, 255, 0.3)");

  const medalhas = [
    { cor: "rgba(200, 210, 220, 0.35)", corMedalha: "#c9d3da", valor: stats.pratas || 0, alturaBarra: 75 },
    { cor: "rgba(255, 215, 90, 0.4)", corMedalha: "#ffd75a", valor: stats.ouros || 0, alturaBarra: 118 },
    { cor: "rgba(205, 140, 90, 0.4)", corMedalha: "#cd8c5a", valor: stats.bronzes || 0, alturaBarra: 55 },
  ];
  const larguraBarra = 200;
  const gapBarra = 40;
  const larguraTotalBarras = larguraBarra * 3 + gapBarra * 2;
  const xInicioBarras = margem + (W - margem * 2 - larguraTotalBarras) / 2;
  const baseBarras = painelY + painelAltura - 36;
  const yMedalha = painelY + 68;

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

    desenharMedalhaColorida(ctx, x + larguraBarra / 2, yMedalha, 30, m.corMedalha);

    ctx.font = "bold 48px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(String(m.valor), x + larguraBarra / 2, yBarra + m.alturaBarra / 2 + 17);
  });

  // Bloco "escaneie" com QR code — link direto pro perfil público (se o
  // atleta já tiver nome de usuário definido) ou pro cadastro (senão,
  // ainda dá pra converter quem só está vendo o Story). Além de reduzir a
  // fricção de digitar a URL, preenche o espaço que sobra até o rodapé em
  // vez de deixar uma faixa vazia — o Stories é vertical (1080×1920) e a
  // maioria dos perfis não enche a tela só com a grade + o pódio.
  const urlQr = perfil.nomeUsuario
    ? `https://www.radarbjj.com/atleta/${encodeURIComponent(perfil.nomeUsuario)}`
    : "https://www.radarbjj.com/cadastro";
  const yQr = painelY + painelAltura + 22;
  const alturaQr = desenharBlocoQrCode(ctx, {
    x: margem,
    y: yQr,
    largura: W - margem * 2,
    url: urlQr,
    titulo: perfil.nomeUsuario ? "Veja meu perfil completo" : "Crie sua conta grátis",
    subtitulo: "Escaneie ou acesse www.radarbjj.com",
  });

  // Rodapé — linha — globo — url — linha, mesmo padrão do Story de Minha
  // Agenda (ver static/agenda.js).
  const urlSite = "www.radarbjj.com";
  const yUrl = Math.min(yQr + alturaQr + 45, H - 90);
  ctx.font = "bold 32px -apple-system, Arial, sans-serif";
  const larguraTextoUrl = ctx.measureText(urlSite).width;
  const larguraBlocoUrl = larguraTextoUrl + 50;
  ctx.strokeStyle = "rgba(127, 212, 255, 0.5)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(60, yUrl);
  ctx.lineTo(W / 2 - larguraBlocoUrl / 2, yUrl);
  ctx.moveTo(W / 2 + larguraBlocoUrl / 2, yUrl);
  ctx.lineTo(W - 60, yUrl);
  ctx.stroke();
  desenharIcone(ctx, "globo", W / 2 - larguraTextoUrl / 2 - 26, yUrl, 26, CIANO, 2.2);
  ctx.fillStyle = "#ffffff";
  ctx.textAlign = "left";
  ctx.fillText(urlSite, W / 2 - larguraTextoUrl / 2 + 4, yUrl + 10);
  ctx.textAlign = "center";

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
checarSessaoCarreira();
