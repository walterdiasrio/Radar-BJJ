const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-agenda");

let itensAtuais = [];

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function badgeStatus(status) {
  return status === "inscrito"
    ? '<span class="badge-inscricao badge-aberta">Inscrição Confirmada</span>'
    : '<span class="badge-inscricao badge-desconhecida">Tenho Interesse</span>';
}

function renderizar(itens) {
  itensAtuais = itens;

  if (!itens.length) {
    elLista.innerHTML = "";
    mostrarStatus('Nenhuma competição marcada ainda. Vá em Competições e marque as que te interessam com "Tenho Interesse" ou "Inscrito".');
    return;
  }
  mostrarStatus("");

  const blocos = [];
  let atual = null;
  for (const item of itens) {
    if (!atual || atual.mes !== item.mes) {
      atual = { mes: item.mes, itens: [] };
      blocos.push(atual);
    }
    atual.itens.push(item);
  }

  elLista.innerHTML = blocos.map(bloco => `
    <section class="secao-mes">
      <div class="bloco-mes">${bloco.mes} <span class="contagem">(${bloco.itens.length})</span></div>
      ${bloco.itens.map(item => `
        <div class="cartao-alerta">
          <div class="cartao-alerta-topo">
            <div>
              <div class="cartao-alerta-federacao">${item.federacao} — ${item.nome}</div>
              <div class="cartao-alerta-filtros">${item.data}${item.local ? " · " + item.local : ""}</div>
            </div>
            <button type="button" class="btn-remover" data-id="${item.id}">Remover</button>
          </div>
          <div style="margin-top:8px;">${badgeStatus(item.status)}</div>
        </div>
      `).join("")}
    </section>
  `).join("");

  elLista.querySelectorAll(".btn-remover").forEach(btn => {
    btn.addEventListener("click", () => remover(Number(btn.dataset.id)));
  });
}

async function carregar() {
  mostrarStatus("Carregando...");
  try {
    const resp = await fetchAutenticado("/api/agenda");
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao carregar agenda");
    renderizar(dados);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function remover(id) {
  const item = itensAtuais.find(i => i.id === id);
  if (!item) return;
  if (!confirm(`Remover "${item.nome}" da sua agenda?`)) return;

  try {
    const resp = await fetchAutenticado("/api/agenda", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ federacao: item.federacao, nome: item.nome, data: item.data }),
    });
    if (!resp.ok) throw new Error("não consegui remover");
    itensAtuais = itensAtuais.filter(i => i.id !== id);
    renderizar(itensAtuais);
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregar();

// ---------- Exportar pro Instagram (Stories) ----------
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
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

function carregarImagem(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

function truncarTexto(ctx, texto, larguraMax) {
  if (ctx.measureText(texto).width <= larguraMax) return texto;
  let cortado = texto;
  while (cortado.length > 1 && ctx.measureText(cortado + "…").width > larguraMax) {
    cortado = cortado.slice(0, -1);
  }
  return cortado + "…";
}

let ultimoBlobAgendaStory = null;

async function gerarImagemAgendaStory() {
  const canvas = document.getElementById("canvas-agenda-story");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const CIANO = "#7fd4ff";
  const CINZA_AZULADO = "#b7cbdc";

  mostrarStatusStory("Gerando imagem...");

  const filtro = document.getElementById("agenda_export_filtro").value;
  const itens = filtro === "inscrito"
    ? itensAtuais.filter(i => i.status === "inscrito")
    : itensAtuais;

  if (!itens.length) {
    mostrarStatusStory(
      filtro === "inscrito"
        ? "Você ainda não tem nenhuma inscrição confirmada na agenda."
        : "Sua agenda está vazia — marque competições em Competições primeiro.",
      true,
    );
    return;
  }

  let nome = "";
  try {
    const respPerfil = await fetchAutenticado("/api/carreira/perfil");
    const perfil = await respPerfil.json();
    nome = perfil.nome || "";
  } catch (err) {
    // segue sem nome — não é essencial pra imagem
  }

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

  let yAposBanner = 280;
  try {
    const banner = await carregarImagem("img/banner.jpg");
    const larguraBanner = 580;
    const alturaBanner = larguraBanner * (banner.height / banner.width);
    ctx.save();
    ctx.shadowColor = "rgba(127, 212, 255, 0.5)";
    ctx.shadowBlur = 30;
    roundRect(ctx, W / 2 - larguraBanner / 2, 70, larguraBanner, alturaBanner, 14);
    ctx.clip();
    ctx.drawImage(banner, W / 2 - larguraBanner / 2, 70, larguraBanner, alturaBanner);
    ctx.restore();
    yAposBanner = 70 + alturaBanner + 40;
  } catch (err) {
    // segue sem o banner se não conseguir carregar
  }

  // "MINHAS PRÓXIMAS COMPETIÇÕES" com tracinhos decorativos, igual ao
  // padrão do "RESUMO DE CARREIRA" em Minha Carreira → Compartilhar.
  ctx.font = "26px -apple-system, Arial, sans-serif";
  ctx.letterSpacing = "3px";
  ctx.fillStyle = CINZA_AZULADO;
  const rotulo = "MINHAS PRÓXIMAS COMPETIÇÕES";
  const larguraRotulo = ctx.measureText(rotulo).width;
  ctx.fillText(rotulo, W / 2, yAposBanner);
  ctx.letterSpacing = "0px";
  ctx.strokeStyle = "rgba(127, 212, 255, 0.7)";
  ctx.lineWidth = 2;
  const xEsq = W / 2 - larguraRotulo / 2 - 40;
  const xDir = W / 2 + larguraRotulo / 2 + 40;
  ctx.beginPath();
  ctx.moveTo(xEsq - 26, yAposBanner - 8);
  ctx.lineTo(xEsq, yAposBanner - 8);
  ctx.moveTo(xDir, yAposBanner - 8);
  ctx.lineTo(xDir + 26, yAposBanner - 8);
  ctx.stroke();

  let yTopo = yAposBanner + 30;
  if (nome) {
    let tamanhoNome = 56;
    ctx.font = `bold ${tamanhoNome}px -apple-system, Arial, sans-serif`;
    while (ctx.measureText(nome).width > W - 120 && tamanhoNome > 32) {
      tamanhoNome -= 4;
      ctx.font = `bold ${tamanhoNome}px -apple-system, Arial, sans-serif`;
    }
    ctx.fillStyle = "#ffffff";
    yTopo += 58;
    ctx.fillText(nome, W / 2, yTopo);
    yTopo += 20;
  }

  // Lista de competições — um cartão por item, com data, evento e o badge
  // de status (Inscrição Confirmada / Tenho Interesse). Cabe um número
  // limitado de cartões no Stories; o resto vira um resumo "+N outras".
  const margem = 60;
  const larguraCartao = W - margem * 2;
  const alturaCartao = 185;
  const gap = 22;
  const yListaTopo = yTopo + 50;
  const alturaDisponivel = H - yListaTopo - 220; // reserva espaço pro rodapé
  const maxCartoes = Math.max(1, Math.floor((alturaDisponivel + gap) / (alturaCartao + gap)));
  const visiveis = itens.slice(0, maxCartoes);
  const restantes = itens.length - visiveis.length;

  visiveis.forEach((item, i) => {
    const y = yListaTopo + i * (alturaCartao + gap);
    const corBorda = item.status === "inscrito" ? "rgba(120, 220, 150, 0.55)" : "rgba(127, 212, 255, 0.4)";
    cartaoComGlow(ctx, margem, y, larguraCartao, alturaCartao, 20, corBorda);

    ctx.textAlign = "left";
    const xTexto = margem + 36;
    const larguraTexto = larguraCartao - 72;

    // Badge fica na mesma linha da data, no canto direito — desenhado
    // primeiro pra já saber a largura disponível pro texto da data (evita
    // sobrepor um no outro em nomes de evento/data mais longos).
    const textoBadge = item.status === "inscrito" ? "INSCRITO" : "INTERESSE";
    const corBadge = item.status === "inscrito" ? "#3fd17e" : "#7fd4ff";
    ctx.font = "bold 22px -apple-system, Arial, sans-serif";
    ctx.letterSpacing = "1px";
    const larguraBadge = ctx.measureText(textoBadge).width + 40;
    const xBadge = margem + larguraCartao - larguraBadge - 30;
    const yBadge = y + 26;
    const alturaBadge = 44;
    ctx.strokeStyle = corBadge;
    ctx.lineWidth = 2;
    roundRect(ctx, xBadge, yBadge, larguraBadge, alturaBadge, alturaBadge / 2);
    ctx.stroke();
    ctx.fillStyle = corBadge;
    ctx.textAlign = "center";
    ctx.fillText(textoBadge, xBadge + larguraBadge / 2, yBadge + 29);
    ctx.letterSpacing = "0px";
    ctx.textAlign = "left";

    const larguraData = xBadge - xTexto - 24;
    ctx.font = "bold 30px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CIANO;
    ctx.fillText(truncarTexto(ctx, item.data || "", larguraData), xTexto, y + 54);

    // Linha do evento começa bem abaixo do fundo do balão de status (y +
    // 70), pra nunca encostar nele mesmo com fontes/métricas diferentes
    // entre navegadores.
    ctx.font = "bold 36px -apple-system, Arial, sans-serif";
    ctx.fillStyle = "#ffffff";
    const linhaEvento = `${item.federacao} — ${item.nome}`;
    ctx.fillText(truncarTexto(ctx, linhaEvento, larguraTexto), xTexto, y + 116);

    if (item.local) {
      ctx.font = "26px -apple-system, Arial, sans-serif";
      ctx.fillStyle = CINZA_AZULADO;
      ctx.fillText(truncarTexto(ctx, item.local, larguraTexto), xTexto, y + 156);
    }
  });
  ctx.textAlign = "center";

  let yFimLista = yListaTopo + visiveis.length * (alturaCartao + gap) - gap;
  if (restantes > 0) {
    ctx.font = "28px -apple-system, Arial, sans-serif";
    ctx.fillStyle = CINZA_AZULADO;
    ctx.fillText(`+ ${restantes} outra(s) competição(ões)`, W / 2, yFimLista + 44);
    yFimLista += 60;
  }

  // Rodapé — link em destaque, mesmo padrão do Compartilhar de Minha Carreira.
  const urlSite = "www.radarbjj.com";
  ctx.font = "bold 40px -apple-system, Arial, sans-serif";
  const larguraUrl = ctx.measureText(urlSite).width + 90;
  const yUrl = Math.min(yFimLista + 90, H - 90);
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
    ultimoBlobAgendaStory = blob;
    canvas.style.display = "block";
    document.getElementById("btn-baixar-agenda-story").classList.remove("hidden");
    if (navigator.share && navigator.canShare && navigator.canShare({ files: [new File([blob], "x.png", { type: "image/png" })] })) {
      document.getElementById("btn-compartilhar-agenda-story").classList.remove("hidden");
    }
    mostrarStatusStory("Imagem gerada!");
  }, "image/png");
}

function mostrarStatusStory(texto, ehErro = false) {
  const el = document.getElementById("status-agenda-story");
  el.textContent = texto;
  el.className = "status-importacao" + (ehErro ? " erro" : "");
}

document.getElementById("btn-gerar-agenda-story").addEventListener("click", gerarImagemAgendaStory);

document.getElementById("btn-baixar-agenda-story").addEventListener("click", () => {
  if (!ultimoBlobAgendaStory) return;
  const url = URL.createObjectURL(ultimoBlobAgendaStory);
  const a = document.createElement("a");
  a.href = url;
  a.download = "radar-bjj-minha-agenda.png";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("btn-compartilhar-agenda-story").addEventListener("click", async () => {
  if (!ultimoBlobAgendaStory) return;
  try {
    await navigator.share({
      files: [new File([ultimoBlobAgendaStory], "radar-bjj-minha-agenda.png", { type: "image/png" })],
      title: "Minhas próximas competições — Radar BJJ",
    });
  } catch (err) {
    // usuário cancelou o compartilhamento — sem problema
  }
});
