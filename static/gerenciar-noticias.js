const elForm = document.getElementById("form-noticia");
const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-noticias");
const elTitulo = document.getElementById("titulo-form");
const elLabelImagem = document.getElementById("label-imagem");
const elImagem = document.getElementById("imagem");
const elBtnPublicar = document.getElementById("btn-publicar");
const elBtnCancelar = document.getElementById("btn-cancelar-edicao");

// Evita repetir o bug real de 11/09/2026: uma data limite digitada errado
// (dia/mês trocado) caiu no passado e a notícia sumiu assim que criada —
// o "min" bloqueia a data no próprio seletor nativo antes de chegar a
// enviar o formulário (o servidor também rejeita, ver noticias.py).
document.getElementById("data_limite").min = new Date().toISOString().slice(0, 10);

let editandoId = null;

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

function iniciarEdicao(n) {
  editandoId = n.id;
  document.getElementById("manchete").value = n.manchete;
  document.getElementById("texto").value = n.texto || "";
  document.getElementById("data_limite").value = n.data_limite || "";
  elImagem.required = false;
  elLabelImagem.textContent = "Foto (deixe em branco pra manter a atual)";
  elTitulo.textContent = "Editar notícia";
  elBtnPublicar.textContent = "Salvar alterações";
  elBtnCancelar.style.display = "";
  elForm.scrollIntoView({ behavior: "smooth", block: "start" });
}

function cancelarEdicao() {
  editandoId = null;
  elForm.reset();
  elImagem.required = true;
  elLabelImagem.textContent = "Foto";
  elTitulo.textContent = "Nova notícia";
  elBtnPublicar.textContent = "Publicar";
  elBtnCancelar.style.display = "none";
}

elBtnCancelar.addEventListener("click", cancelarEdicao);

async function carregarLista() {
  elLista.innerHTML = "";
  try {
    const resp = await fetchAutenticado("/api/noticias/admin");
    const lista = await resp.json();
    if (!lista.length) {
      elLista.innerHTML = "<p>Nenhuma notícia publicada ainda.</p>";
      return;
    }
    const hoje = new Date().toISOString().slice(0, 10);
    elLista.innerHTML = lista.map(n => {
      const expirada = n.data_limite && n.data_limite < hoje;
      return `
      <div class="noticia-item">
        <img src="${n.imagem_url}" alt="${n.manchete}">
        <div class="noticia-manchete">
          ${n.manchete}
          ${n.data_limite ? `<div style="font-weight:400; font-size:0.8rem; color:${expirada ? "#c0392b" : "#55606b"};">${expirada ? "expirou em" : "expira em"} ${n.data_limite.split("-").reverse().join("/")}</div>` : ""}
        </div>
        <button class="btn-editar" data-id="${n.id}">Editar</button>
        <button class="btn-remover" data-id="${n.id}">Remover</button>
      </div>
    `;
    }).join("");

    elLista.querySelectorAll(".btn-editar").forEach(btn => {
      const n = lista.find(item => String(item.id) === btn.dataset.id);
      btn.addEventListener("click", () => iniciarEdicao(n));
    });
    elLista.querySelectorAll(".btn-remover").forEach(btn => {
      btn.addEventListener("click", () => remover(btn.dataset.id));
    });
  } catch (err) {
    elLista.innerHTML = `<p class="erro">Erro ao carregar: ${err.message}</p>`;
  }
}

async function remover(id) {
  if (!confirm("Remover essa notícia?")) return;
  try {
    const resp = await fetchAutenticado(`/api/noticias/${id}`, { method: "DELETE" });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao remover");
    if (String(editandoId) === String(id)) cancelarEdicao();
    carregarLista();
  } catch (err) {
    mostrarStatus(`Erro ao remover: ${err.message}`, true);
  }
}

elForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const manchete = document.getElementById("manchete").value;
  const texto = document.getElementById("texto").value;
  const dataLimite = document.getElementById("data_limite").value;
  const arquivo = elImagem.files[0];
  if (!arquivo && !editandoId) return;

  const formData = new FormData();
  formData.append("manchete", manchete);
  formData.append("texto", texto);
  formData.append("data_limite", dataLimite);
  if (arquivo) formData.append("imagem", arquivo);

  const editando = editandoId;
  mostrarStatus(editando ? "Salvando..." : "Publicando...");

  try {
    const resp = await fetchAutenticado(
      editando ? `/api/noticias/${editando}` : "/api/noticias",
      { method: editando ? "PUT" : "POST", body: formData },
    );
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao publicar");

    mostrarStatus(editando ? "Alterações salvas!" : "Notícia publicada!");
    cancelarEdicao();
    carregarLista();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});

carregarLista();
