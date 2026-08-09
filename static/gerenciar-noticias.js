const elForm = document.getElementById("form-noticia");
const elStatus = document.getElementById("status");
const elLista = document.getElementById("lista-noticias");

function mostrarStatus(texto, ehErro = false) {
  elStatus.textContent = texto;
  elStatus.className = "status-importacao" + (ehErro ? " erro" : "");
}

async function carregarLista() {
  elLista.innerHTML = "";
  try {
    const resp = await fetchAutenticado("/api/noticias");
    const lista = await resp.json();
    if (!lista.length) {
      elLista.innerHTML = "<p>Nenhuma notícia publicada ainda.</p>";
      return;
    }
    elLista.innerHTML = lista.map(n => `
      <div class="noticia-item">
        <img src="${n.imagem_url}" alt="${n.manchete}">
        <div class="noticia-manchete">
          ${n.manchete}
          ${n.data_limite ? `<div style="font-weight:400; font-size:0.8rem; color:#7c8894;">expira em ${n.data_limite.split("-").reverse().join("/")}</div>` : ""}
        </div>
        <button class="btn-remover" data-id="${n.id}">Remover</button>
      </div>
    `).join("");

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
  const arquivo = document.getElementById("imagem").files[0];
  if (!arquivo) return;

  const formData = new FormData();
  formData.append("manchete", manchete);
  formData.append("texto", texto);
  formData.append("data_limite", dataLimite);
  formData.append("imagem", arquivo);

  mostrarStatus("Publicando...");

  try {
    const resp = await fetchAutenticado("/api/noticias", { method: "POST", body: formData });
    const dados = await resp.json();
    if (!resp.ok) throw new Error(dados.erro || "erro ao publicar");

    mostrarStatus("Notícia publicada!");
    elForm.reset();
    carregarLista();
  } catch (err) {
    mostrarStatus(`Erro: ${err.message}`, true);
  }
});

carregarLista();
