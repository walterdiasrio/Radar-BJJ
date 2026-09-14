const elStatus = document.getElementById("status");
const elCartaoPerfil = document.getElementById("cartao-perfil");
const elListaCompeticoes = document.getElementById("lista-competicoes");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarData(data) {
  if (!data) return "";
  const iso = data.includes("T") ? data : data + "T00:00:00";
  return new Date(iso).toLocaleDateString("pt-BR");
}

// Página pública é uma vitrine de conquistas, não o histórico completo de
// Minha Carreira — sem lutas/adversários (pedido do usuário), só o essencial
// de cada competição, agrupada por medalha logo abaixo.
function cardCompeticaoPublico(c) {
  const internacional = !!(c.pais && c.pais !== "Brasil");
  const metaPartes = [formatarData(c.data)];
  if (c.categoria) metaPartes.push(c.categoria);
  const tagInternacional = internacional
    ? `<span class="tag-carreira pais">🌎 ${c.pais}</span>`
    : "";
  return `
    <div class="cartao-alerta${internacional ? " cartao-alerta-internacional" : ""}">
      <div class="cartao-alerta-topo">
        <div>
          <h3>${tagInternacional}${c.campeonato || "Competição"}</h3>
          <div class="cartao-alerta-federacao">${metaPartes.join(" · ")}</div>
        </div>
      </div>
    </div>`;
}

// Divide as competições com medalha em 3 grupos (ouro/prata/bronze) — quem
// não pontuou no pódio não entra aqui (já conta pro total de "lutas" nas
// Estatísticas ali em cima).
const GRUPOS_MEDALHA = [
  { chave: "ouro", label: "🥇 Ouro" },
  { chave: "prata", label: "🥈 Prata" },
  { chave: "bronze", label: "🥉 Bronze" },
];

function renderCompeticoesPublicas(competicoes) {
  const grupos = GRUPOS_MEDALHA
    .map(g => ({ ...g, itens: competicoes.filter(c => c.medalha === g.chave) }))
    .filter(g => g.itens.length);

  if (!grupos.length) {
    elListaCompeticoes.innerHTML = "";
    return false;
  }
  elListaCompeticoes.innerHTML = grupos.map(g => `
    <div class="secao-medalhas-publico">
      <h4 class="titulo-secao-medalhas">${g.label} <span class="contagem-medalhas">(${g.itens.length})</span></h4>
      ${g.itens.map(cardCompeticaoPublico).join("")}
    </div>
  `).join("");
  return true;
}

// Pizza de lutas (Vitórias/Derrotas/Empates) via círculos SVG empilhados
// com stroke-dasharray — mesma técnica de gráfico donut padrão, sem
// precisar calcular caminho de arco (path) na mão.
function desenharPizzaLutas(stats) {
  const svg = document.getElementById("grafico-pizza-lutas");
  const elLegenda = document.getElementById("legenda-pizza-lutas");
  const total = stats.lutas || 0;

  if (!total) {
    svg.innerHTML = `<circle cx="50" cy="50" r="40" fill="none" stroke="#e2e6ea" stroke-width="16"/>`;
    elLegenda.innerHTML = `<p style="color:#55606b; font-size:0.85rem; margin:0;">Sem lutas registradas ainda.</p>`;
    return;
  }

  const fatias = [
    { label: "Vitórias", valor: stats.vitorias || 0, cor: "#4caf50" },
    { label: "Derrotas", valor: stats.derrotas || 0, cor: "#ef5350" },
    { label: "Empates", valor: stats.empates || 0, cor: "#f9a825" },
  ].filter(f => f.valor > 0);

  const raio = 40;
  const circunferencia = 2 * Math.PI * raio;
  let acumulado = 0;
  svg.innerHTML = fatias.map(f => {
    const comprimento = (f.valor / total) * circunferencia;
    const el = `<circle cx="50" cy="50" r="${raio}" fill="none" stroke="${f.cor}" stroke-width="16"
      stroke-dasharray="${comprimento} ${circunferencia - comprimento}"
      stroke-dashoffset="${-acumulado}" transform="rotate(-90 50 50)"/>`;
    acumulado += comprimento;
    return el;
  }).join("");

  elLegenda.innerHTML = `
    <div style="font-size:1.4rem; font-weight:700; color:var(--azul);">${total} luta${total === 1 ? "" : "s"}</div>
    ${fatias.map(f => `
      <div class="legenda-pizza-item">
        <span class="legenda-pizza-bolinha" style="background:${f.cor};"></span>
        ${f.label}
        <span class="legenda-pizza-valor">${f.valor}</span>
      </div>`).join("")}
  `;
}

function mostrarEstatisticas(stats) {
  if (!stats.competicoes) return; // sem nenhuma competição registrada — mantém o cartão escondido
  document.getElementById("cartao-estatisticas").style.display = "";
  desenharPizzaLutas(stats);
  document.getElementById("grade-medalhas-publico").innerHTML = `
    <div class="stat-box"><div class="stat-value">🥇 ${stats.ouros || 0}</div><div class="stat-label">Ouros</div></div>
    <div class="stat-box"><div class="stat-value">🥈 ${stats.pratas || 0}</div><div class="stat-label">Pratas</div></div>
    <div class="stat-box"><div class="stat-value">🥉 ${stats.bronzes || 0}</div><div class="stat-label">Bronzes</div></div>
  `;
}

async function carregarAtletaPublico() {
  const nomeUsuario = window.location.pathname.split("/").filter(Boolean).pop();
  try {
    const resp = await fetch(`/api/atleta-publico/${encodeURIComponent(nomeUsuario)}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "atleta não encontrado");

    document.title = `Radar BJJ — ${dados.perfil.nome || nomeUsuario}`;
    mostrarStatus("");

    elCartaoPerfil.style.display = "";
    // Foto 2x maior (88px -> 176px) a pedido do usuário.
    document.getElementById("perfil-foto").innerHTML = dados.perfil.foto_url
      ? `<img src="${dados.perfil.foto_url}" alt="" style="width:176px; height:176px; border-radius:50%; object-fit:cover; border:2px solid var(--borda);">`
      : `<div style="width:176px; height:176px; border-radius:50%; background:var(--campo-bg); border:2px solid var(--borda); display:flex; align-items:center; justify-content:center; font-size:4.4rem; margin:0 auto;">🥋</div>`;
    document.getElementById("perfil-nome").textContent = dados.perfil.nome || `@${nomeUsuario}`;
    document.getElementById("perfil-faixa").textContent =
      `Faixa ${dados.perfil.faixa}${Number(dados.perfil.grau) > 0 ? " · " + dados.perfil.grau + "º grau" : ""}`;
    document.getElementById("perfil-academia").textContent = dados.perfil.academia || "";

    if (dados.estatisticas) mostrarEstatisticas(dados.estatisticas);

    const teveMedalhas = renderCompeticoesPublicas(dados.competicoes || []);
    document.getElementById("titulo-competicoes").style.display = teveMedalhas ? "" : "none";
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregarAtletaPublico();
