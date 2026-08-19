const elStatus = document.getElementById("status");
const elCartaoPerfil = document.getElementById("cartao-perfil");
const elListaCompeticoes = document.getElementById("lista-competicoes");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

const MEDALHA_LABEL = { ouro: "🥇 Ouro", prata: "🥈 Prata", bronze: "🥉 Bronze" };
const RESULTADO_LABEL = { vitoria: "Vitória", derrota: "Derrota", empate: "Empate" };
const METODO_LABEL = { pontos: "Pontos", finalizacao: "Finalização", wo: "W.O.", desclassificacao: "Desclassificação", medica: "Médica" };

function formatarData(data) {
  if (!data) return "";
  const iso = data.includes("T") ? data : data + "T00:00:00";
  return new Date(iso).toLocaleDateString("pt-BR");
}

function cardCompeticaoPublico(c) {
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

async function carregarAtletaPublico() {
  const nomeUsuario = window.location.pathname.split("/").filter(Boolean).pop();
  try {
    const resp = await fetch(`/api/atleta-publico/${encodeURIComponent(nomeUsuario)}`);
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "atleta não encontrado");

    document.title = `Radar BJJ — ${dados.perfil.nome || nomeUsuario}`;
    mostrarStatus("");

    elCartaoPerfil.style.display = "";
    document.getElementById("perfil-foto").innerHTML = dados.perfil.foto_url
      ? `<img src="${dados.perfil.foto_url}" alt="" style="width:88px; height:88px; border-radius:50%; object-fit:cover; border:2px solid var(--borda);">`
      : `<div style="width:88px; height:88px; border-radius:50%; background:var(--campo-bg); border:2px solid var(--borda); display:flex; align-items:center; justify-content:center; font-size:2.2rem; margin:0 auto;">🥋</div>`;
    document.getElementById("perfil-nome").textContent = dados.perfil.nome || `@${nomeUsuario}`;
    document.getElementById("perfil-faixa").textContent =
      `Faixa ${dados.perfil.faixa}${Number(dados.perfil.grau) > 0 ? " · " + dados.perfil.grau + "º grau" : ""}`;
    document.getElementById("perfil-academia").textContent = dados.perfil.academia || "";

    if (!dados.competicoes.length) {
      elListaCompeticoes.innerHTML = "";
      return;
    }
    document.getElementById("titulo-competicoes").style.display = "";
    elListaCompeticoes.innerHTML = dados.competicoes.map(cardCompeticaoPublico).join("");
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregarAtletaPublico();
