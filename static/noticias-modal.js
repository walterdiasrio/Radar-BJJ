// Compartilhado: modal de notícia ampliada, usado tanto no destaque da
// home quanto na página BJJ News.
function _montarModalNoticia() {
  if (document.getElementById("noticia-modal-overlay")) return;
  const div = document.createElement("div");
  div.id = "noticia-modal-overlay";
  div.className = "noticia-modal-overlay escondido";
  div.innerHTML = `
    <div class="noticia-modal">
      <button type="button" class="noticia-modal-fechar" aria-label="Fechar">&times;</button>
      <img id="noticia-modal-img" src="" alt="">
      <div class="noticia-modal-manchete" id="noticia-modal-manchete"></div>
      <div class="noticia-modal-texto" id="noticia-modal-texto"></div>
    </div>
  `;
  document.body.appendChild(div);
  div.addEventListener("click", (ev) => { if (ev.target === div) fecharNoticiaModal(); });
  div.querySelector(".noticia-modal-fechar").addEventListener("click", fecharNoticiaModal);
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") fecharNoticiaModal(); });
}

function abrirNoticiaModal(imagemUrl, manchete, texto) {
  _montarModalNoticia();
  document.getElementById("noticia-modal-img").src = imagemUrl;
  document.getElementById("noticia-modal-img").alt = manchete;
  document.getElementById("noticia-modal-manchete").textContent = manchete;
  document.getElementById("noticia-modal-texto").textContent = texto || "";
  document.getElementById("noticia-modal-overlay").classList.remove("escondido");
}

function fecharNoticiaModal() {
  const el = document.getElementById("noticia-modal-overlay");
  if (el) el.classList.add("escondido");
}
