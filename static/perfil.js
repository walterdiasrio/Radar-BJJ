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

    let nomeUsuario = "";
    try {
      const respNU = await fetchAutenticado("/api/conta/nome-usuario");
      nomeUsuario = (await respNU.json()).nome_usuario || "";
    } catch (err) {
      // segue sem nome de usuário carregado
    }
    atualizarLembretePerfil(p, nomeUsuario);
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

// Aviso fixo enquanto faltar nome de usuário ou academia — sem os dois
// preenchidos, o vínculo com Mestre/Alunos não funciona.
function atualizarLembretePerfil(perfil, nomeUsuario) {
  const elAviso = document.getElementById("lembrete-perfil");
  const faltando = [];
  if (!(nomeUsuario || "").trim()) faltando.push("nome de usuário");
  if (!(perfil.academia || "").trim()) faltando.push("academia");

  if (!faltando.length) {
    elAviso.style.display = "none";
    return;
  }
  document.getElementById("lembrete-perfil-texto").textContent =
    `Falta preencher: ${faltando.join(" e ")}. Isso é essencial para o vínculo Mestre/Alunos funcionar corretamente.`;
  elAviso.style.display = "flex";
}

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
    atualizarLembretePerfil(dados, document.getElementById("nome_usuario").value);
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
    atualizarLembretePerfil({ academia: document.getElementById("p_academia").value }, nomeUsuario);
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
    el.innerHTML = mestres.map(m => {
      const pendente = m.vinculo_status === "pendente";
      // Pendente porque o MESTRE convidou: a bola é do aluno (Aceitar/
      // Recusar aqui mesmo). Pendente porque o ALUNO pediu: só falta o
      // mestre aceitar do lado dele — aqui só dá pra cancelar o pedido.
      const precisaAceitar = pendente && m.vinculo_criado_por === "mestre";
      return `
      <div class="cartao-alerta" style="margin-bottom: 8px;">
        <div class="cartao-alerta-topo">
          <div>
            <h3 style="font-size: 0.95rem;">${m.nome || "(sem nome)"}</h3>
            ${pendente
              ? `<div class="cartao-alerta-federacao">${precisaAceitar ? "Convidou você — pendente" : "Pedido enviado — aguardando aceite"}</div>`
              : (m.academia ? `<div class="cartao-alerta-federacao">${m.academia}</div>` : "")}
          </div>
          <div style="display:flex; gap:8px;">
            ${precisaAceitar ? `<button type="button" class="btn-aceitar-vinculo" data-id="${m.usuario_id}">Aceitar</button>` : ""}
            <button type="button" class="btn-remover" data-id="${m.usuario_id}">${pendente ? (precisaAceitar ? "Recusar" : "Cancelar") : "Remover"}</button>
          </div>
        </div>
      </div>
    `;
    }).join("");
    el.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => removerMestre(Number(btn.dataset.id)));
    });
    el.querySelectorAll(".btn-aceitar-vinculo").forEach(btn => {
      btn.addEventListener("click", () => aceitarMestre(Number(btn.dataset.id)));
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
    mostrarStatus("status-mestre", "Pedido enviado! Fica pendente até o Mestre aceitar.");
    elInput.value = "";
    carregarMestres();
  } catch (err) {
    mostrarStatus("status-mestre", `Erro: ${err.message}`, true);
  }
});

async function aceitarMestre(mestreId) {
  try {
    const resp = await fetchAutenticado(`/api/carreira/meu-mestre/${mestreId}/aceitar`, { method: "POST" });
    if (!resp.ok) throw new Error("não consegui aceitar");
    mostrarStatus("status-mestre", "Vínculo aceito!");
    carregarMestres();
  } catch (err) {
    mostrarStatus("status-mestre", `Erro: ${err.message}`, true);
  }
}

async function removerMestre(mestreId) {
  try {
    const resp = await fetchAutenticado(`/api/carreira/meu-mestre/${mestreId}`, { method: "DELETE" });
    if (!resp.ok) throw new Error("não consegui remover");
    carregarMestres();
  } catch (err) {
    mostrarStatus("status-mestre", `Erro: ${err.message}`, true);
  }
}

// ---------- Trocar perfil pra Mestre ----------
// No Free, a troca é imediata (não tem assinatura de Atleta "presa" pra
// dessincronizar). Assinando Atleta PRO, o back recusa com 402 e manda
// assinar o Mestre PRO em vez de só virar o tipo_perfil (ver
// api_tornar_mestre em app.py).
async function checarTipoPerfilESessao() {
  try {
    const resp = await fetch("/api/sessao");
    const dados = await resp.json();

    const elCardMestre = document.getElementById("card-meu-mestre");
    if (elCardMestre) elCardMestre.style.display = dados.mestre ? "none" : "";

    const elTextoInstrucao = document.getElementById("texto-nome-usuario-instrucao");
    if (elTextoInstrucao && dados.mestre) {
      elTextoInstrucao.textContent = "Compartilhe o seu login com seus alunos e peça-os para o adicionar como Mestre no Perfil.";
    }

    const elCardTornarMestre = document.getElementById("card-tornar-mestre");
    if (elCardTornarMestre) elCardTornarMestre.style.display = dados.tipo_perfil === "atleta" ? "block" : "none";
  } catch (err) {
    // sessão não carregou — segue sem esconder nada
  }
}

document.getElementById("btn-tornar-mestre").addEventListener("click", async () => {
  if (!confirm("Trocar seu perfil de Atleta pra Mestre?")) return;
  try {
    const resp = await fetchAutenticado("/api/conta/tornar-mestre", { method: "POST" });
    const dados = await resp.json();
    if (resp.status === 402 && dados.precisa_assinar_mestre) {
      mostrarStatus("status-tornar-mestre", "Sua assinatura é do Atleta PRO — te levando pra assinar o Mestre PRO...", true);
      window.location.href = "/assinatura?plano=mestre";
      return;
    }
    if (!resp.ok) throw new Error(dados.erro || "não consegui trocar o perfil");
    mostrarStatus("status-tornar-mestre", "Perfil trocado pra Mestre! Recarregando...");
    window.location.reload();
  } catch (err) {
    mostrarStatus("status-tornar-mestre", `Erro: ${err.message}`, true);
  }
});

// ---------- Trocar senha ----------
document.getElementById("form-senha").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const elSenhaAtual = document.getElementById("senha_atual");
  const elNovaSenha = document.getElementById("nova_senha");
  const elConfirmar = document.getElementById("confirmar_nova_senha");

  if (elNovaSenha.value !== elConfirmar.value) {
    mostrarStatus("status-senha", "A nova senha e a confirmação são diferentes.", true);
    return;
  }

  try {
    const resp = await fetchAutenticado("/api/conta/senha", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ senha_atual: elSenhaAtual.value, nova_senha: elNovaSenha.value }),
    });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "não consegui trocar a senha");
    mostrarStatus("status-senha", "Senha trocada!");
    document.getElementById("form-senha").reset();
  } catch (err) {
    mostrarStatus("status-senha", `Erro: ${err.message}`, true);
  }
});

// ---------- Init ----------
carregarPerfil();
carregarNomeUsuario();
carregarMestres();
checarTipoPerfilESessao();
