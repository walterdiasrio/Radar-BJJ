const elStatus = document.getElementById("status");
const elConteudo = document.getElementById("conteudo-aluno");

const RESULTADO_LABEL = { vitoria: "Vitória", derrota: "Derrota", empate: "Empate" };
const METODO_LABEL = { pontos: "Pontos", finalizacao: "Finalização", wo: "W.O.", desclassificacao: "Desclassificação", medica: "Médica" };
const MEDALHA_LABEL = { ouro: "🥇 Ouro", prata: "🥈 Prata", bronze: "🥉 Bronze" };

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarData(data) {
  if (!data) return "";
  const iso = data.includes("T") ? data : data + "T00:00:00";
  return new Date(iso).toLocaleDateString("pt-BR");
}

function cardCompeticao(c) {
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
      </div>
      <div class="lutas-list">${lutasHtml}</div>
    </div>`;
}

function desenharGrafico(svg, pontos) {
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

async function carregar() {
  const usuarioId = window.location.pathname.split("/").pop();
  try {
    const resp = await fetchAutenticado(`/api/meus-alunos/${usuarioId}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar aluno");

    const p = dados.perfil;
    const s = dados.estatisticas;

    const stats = [
      { label: "Competições", value: s.competicoes },
      { label: "Lutas", value: s.lutas },
      { label: "Vitórias", value: s.vitorias },
      { label: "Derrotas", value: s.derrotas },
      { label: "Taxa de vitória", value: s.taxa_vitoria + "%" },
      { label: "Melhor sequência", value: s.melhor_sequencia },
      { label: "Finalizações", value: s.finalizacoes },
      { label: "Campeonatos diferentes", value: s.campeonatos_diferentes },
      { label: "🥇 Ouros", value: s.ouros },
      { label: "🥈 Pratas", value: s.pratas },
      { label: "🥉 Bronzes", value: s.bronzes },
    ];

    elConteudo.innerHTML = `
      <div class="card-carreira" style="max-width: 480px;">
        <h2 style="margin-top: 0; color: var(--azul);">${p.nome || "(sem nome)"}</h2>
        <p style="color: #7c8894; margin: 0 0 4px;">
          Faixa ${p.faixa}${Number(p.grau) > 0 ? " · " + p.grau + "º grau" : ""}
          ${p.categoria ? " · " + p.categoria : ""}
        </p>
        ${p.academia ? `<p style="color: #7c8894; margin: 0;">${p.academia}</p>` : ""}
        ${dados.email ? `<p style="color: #7c8894; margin: 4px 0 0; font-size: 0.85rem;">${dados.email}</p>` : ""}
      </div>

      <h3 style="color: var(--azul); margin: 24px 0 12px;">Estatísticas</h3>
      <div class="stats-grid">
        ${stats.map(item => `
          <div class="stat-box">
            <div class="stat-value">${item.value}</div>
            <div class="stat-label">${item.label}</div>
          </div>`).join("")}
      </div>
      <div class="card-carreira" style="max-width: 100%;">
        <h3 style="color: var(--azul); margin-top: 0;">Evolução de vitórias ao longo do tempo</h3>
        <svg id="grafico-aluno" viewBox="0 0 600 240" preserveAspectRatio="xMidYMid meet" style="width: 100%; height: auto;"></svg>
      </div>

      <h3 style="color: var(--azul); margin: 24px 0 12px;">Histórico de competições</h3>
      <div id="lista-historico-aluno">
        ${dados.competicoes.length ? dados.competicoes.map(cardCompeticao).join("") : '<p style="color:#7c8894;">Nenhum registro ainda.</p>'}
      </div>
    `;

    desenharGrafico(document.getElementById("grafico-aluno"), s.grafico || []);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregar();
