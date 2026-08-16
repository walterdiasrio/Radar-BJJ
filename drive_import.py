"""Importação automática de eventos ADCC/AJP a partir de uma pasta do Google
Drive, verificada 1x por dia às 20h (horário de Brasília) — complementa a
importação manual (páginas /importar-adcc e /importar-ajp), mesma lógica de
parsing, só que os arquivos HTML vêm do Drive em vez de upload manual.

Estrutura esperada na pasta do Drive (uma por federação, ids fixos abaixo):
  Nome do Evento.html            → página do evento (Passo 1 manual)
  Nome do Evento - atletas.html  → página "Athletes"/inscritos (Passo 2 manual)
Depois de importado com sucesso, os dois arquivos são movidos pra dentro da
subpasta "Processados" daquela federação — assim a pasta principal sempre
mostra só o que ainda falta processar, e nada é reimportado por engano.

Precisa da credencial de uma Service Account do Google Cloud (com acesso de
Editor nas pastas abaixo) na variável de ambiente GOOGLE_SERVICE_ACCOUNT_JSON
(o JSON inteiro da chave, como texto) — sem ela, verificar_e_importar() só
avisa que está desativado e não faz nada (não é erro fatal pro site subir).
"""
import json
import os
import threading
import time
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from connectors import adcc, ajp

FOLDER_ADCC = "1RqVHMayyyGm_kyoGnMc9oHs4PzByonz8"
FOLDER_ADCC_PROCESSADOS = "11ep8NCPFV0sms5Ps8hs6Gx2GppWihdLg"
FOLDER_AJP = "1Ri7xeHSodSug1G-lgeSo9jNAdzkeCQqL"
FOLDER_AJP_PROCESSADOS = "1z5D71hc5b4i2VndmbYSZyR-fEWo35kOr"

SUFIXO_ATLETAS = " - atletas"

FEDERACOES = [
    ("ADCC", adcc, FOLDER_ADCC, FOLDER_ADCC_PROCESSADOS),
    ("AJP", ajp, FOLDER_AJP, FOLDER_AJP_PROCESSADOS),
]


def _cliente_drive():
    bruto = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not bruto:
        return None
    # Import tardio: essas libs só existem em produção (requirements.txt),
    # sem elas instaladas localmente o resto do site continua funcionando.
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(bruto)
    credenciais = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=credenciais, cache_discovery=False)


def _listar_htmls(drive, folder_id):
    resposta = drive.files().list(
        q=f"'{folder_id}' in parents and trashed = false and mimeType != 'application/vnd.google-apps.folder'",
        fields="files(id, name)",
        pageSize=200,
    ).execute()
    return resposta.get("files", [])


def _baixar_texto(drive, file_id):
    return drive.files().get_media(fileId=file_id).execute().decode("utf-8", errors="replace")


def _mover_para_processados(drive, file_id, origem_folder_id, destino_folder_id):
    drive.files().update(
        fileId=file_id, addParents=destino_folder_id, removeParents=origem_folder_id, fields="id, parents",
    ).execute()


def _nome_arquivo_atletas(nome_evento):
    base, ext = os.path.splitext(nome_evento)
    return f"{base}{SUFIXO_ATLETAS}{ext or '.html'}"


def _processar_par(drive, modulo, arquivo_evento, arquivo_atletas, origem_folder_id, destino_folder_id, log):
    nome = arquivo_evento["name"]
    try:
        evento = modulo.parse_evento_html(_baixar_texto(drive, arquivo_evento["id"]))
        modulo.salvar_evento(evento)

        atletas = modulo.parse_atletas_html(_baixar_texto(drive, arquivo_atletas["id"]))
        if not atletas:
            raise ValueError("nenhum atleta encontrado no arquivo de atletas")
        modulo.salvar_atletas(evento["id"], atletas)

        _mover_para_processados(drive, arquivo_evento["id"], origem_folder_id, destino_folder_id)
        _mover_para_processados(drive, arquivo_atletas["id"], origem_folder_id, destino_folder_id)
        log.append(f"OK: {nome} ({len(atletas)} atletas)")
    except Exception as exc:
        traceback.print_exc()
        log.append(f"ERRO: {nome}: {exc}")


def _processar_pasta(drive, federacao, modulo, origem_folder_id, destino_folder_id, log):
    arquivos = _listar_htmls(drive, origem_folder_id)
    por_nome = {a["name"]: a for a in arquivos}
    eventos = [a for a in arquivos if not a["name"].endswith(f"{SUFIXO_ATLETAS}.html")]
    for arquivo_evento in eventos:
        arquivo_atletas = por_nome.get(_nome_arquivo_atletas(arquivo_evento["name"]))
        if not arquivo_atletas:
            log.append(f"{federacao} pendente: {arquivo_evento['name']} sem o arquivo ' - atletas' ainda")
            continue
        _processar_par(drive, modulo, arquivo_evento, arquivo_atletas, origem_folder_id, destino_folder_id, log)


def verificar_e_importar():
    """Roda uma verificação completa (chamada pelo agendador diário, ou
    manualmente via admin). Retorna a lista de mensagens de log."""
    drive = _cliente_drive()
    if not drive:
        return ["GOOGLE_SERVICE_ACCOUNT_JSON não configurada — importação automática do Drive desativada."]
    log = []
    for federacao, modulo, origem, destino in FEDERACOES:
        try:
            _processar_pasta(drive, federacao, modulo, origem, destino, log)
        except Exception as exc:
            traceback.print_exc()
            log.append(f"{federacao}: erro ao acessar a pasta do Drive: {exc}")
    if not log:
        log.append("Nada novo pra importar.")
    return log


def _iniciar_agendador_diario(hora=20, minuto=0):
    """Dorme até a próxima ocorrência de hora:minuto (horário de Brasília) e
    roda verificar_e_importar(), em loop — 1 verificação por dia."""
    def loop():
        fuso = ZoneInfo("America/Sao_Paulo")
        while True:
            agora = datetime.now(fuso)
            proxima = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
            if proxima <= agora:
                proxima += timedelta(days=1)
            time.sleep((proxima - agora).total_seconds())
            try:
                for linha in verificar_e_importar():
                    print(f"[drive_import] {linha}")
            except Exception:
                traceback.print_exc()

    threading.Thread(target=loop, daemon=True).start()
