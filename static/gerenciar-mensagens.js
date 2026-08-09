const elLista = document.getElementById("lista-mensagens");
const elStatus = document.getElementById("status");

const ASSUNTO_LABEL = {
  duvida: "Dúvida",
  sugestao: "Sugestão",
  problema_tecnico: "Problema técnico",
  assinatura: "Assinatura/Cobrança",
  parceria: "Parceria/Patrocínio",
  outro: "Outro",
};

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function formatarData(data) {
  if (!data) return "";
  return new Date(data.replace(" ", "T") + "Z").toLocaleString("pt-BR");
}

async function carregarMensagens() {
  try {
    const resp = await fetchAutenticado("/api/contato");
    const mensagens = await resp.json();
    if (!mensagens.length) {
      elLista.innerHTML = "<p>Nenhuma mensagem recebida ainda.</p>";
      return;
    }
    elLista.innerHTML = mensagens.map(m => `
      <div class="cartao-alerta" style="${m.lida ? "opacity: 0.7;" : "border-left: 3px solid var(--azul-claro);"}">
        <div class="cartao-alerta-topo">
          <div>
            <h3>${m.nome} ${m.lida ? "" : '<span class="tag-carreira vitoria">Nova</span>'}</h3>
            <div class="cartao-alerta-federacao">${m.email} · ${ASSUNTO_LABEL[m.assunto] || m.assunto} · ${formatarData(m.criado_em)}</div>
          </div>
          <div style="display:flex; gap: 6px; flex-shrink: 0;">
            <button type="button" class="btn-secundario btn-alternar-lida" data-id="${m.id}" data-lida="${m.lida}">${m.lida ? "Marcar não lida" : "Marcar lida"}</button>
            <button type="button" class="btn-remover" data-id="${m.id}">Remover</button>
          </div>
        </div>
        <p style="white-space: pre-wrap; margin-top: 10px; margin-bottom: 0;">${m.mensagem}</p>
      </div>
    `).join("");

    elLista.querySelectorAll(".btn-alternar-lida").forEach(btn => {
      btn.addEventListener("click", () => alternarLida(Number(btn.dataset.id), btn.dataset.lida !== "1"));
    });
    elLista.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => removerMensagem(Number(btn.dataset.id)));
    });
  } catch (err) {
    elLista.innerHTML = `<p class="erro">Erro ao carregar: ${err.message}</p>`;
  }
}

async function alternarLida(id, novoEstadoLida) {
  try {
    const resp = await fetchAutenticado(`/api/contato/${id}/lida`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lida: novoEstadoLida }),
    });
    if (!resp.ok) throw new Error("erro ao atualizar");
    carregarMensagens();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

async function removerMensagem(id) {
  if (!confirm("Remover esta mensagem?")) return;
  try {
    const resp = await fetchAutenticado(`/api/contato/${id}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("erro ao remover");
    carregarMensagens();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
}

carregarMensagens();
