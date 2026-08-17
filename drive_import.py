"""Importação automática de eventos ADCC/AJP a partir de uma pasta do Google
Drive, verificada 1x por dia às 20h (horário de Brasília) — complementa a
importação manual (páginas /importar-adcc e /importar-ajp), mesma lógica de
parsing, só que os arquivos HTML vêm do Drive em vez de upload manual.

Estrutura esperada na pasta do Drive (uma por federação, ids fixos abaixo):
  página do evento (Passo 1 manual) e página "Athletes"/participantes (Passo
  2 manual), salvas do navegador ("Salvar como") sem precisar renomear —
  o casamento entre as duas é tolerante ao nome que o navegador gera
  sozinho (baseado no <title> de cada página, que vem diferente entre elas;
  ver _nome_normalizado). Basta a de atletas ter "participants"/"atletas"/
  "athletes" em algum lugar do nome, o que já é o padrão do Smoothcomp.
Depois de importado com sucesso, os dois arquivos são movidos pra dentro da
subpasta "Processados" daquela federação — assim a pasta principal sempre
mostra só o que ainda falta processar, e nada é reimportado por engano.

Precisa da credencial de uma Service Account do Google Cloud (com acesso de
Editor nas pastas abaixo) na variável de ambiente GOOGLE_SERVICE_ACCOUNT_JSON
(o JSON inteiro da chave, como texto) — sem ela, verificar_e_importar() só
avisa que está desativado e não faz nada (não é erro fatal pro site subir).
"""
import base64
import json
import os
import re
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

FEDERACOES = [
    ("ADCC", adcc, FOLDER_ADCC, FOLDER_ADCC_PROCESSADOS),
    ("AJP", ajp, FOLDER_AJP, FOLDER_AJP_PROCESSADOS),
]


def _cliente_drive():
    bruto = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    if not bruto:
        return None
    # Import tardio: essas libs só existem em produção (requirements.txt),
    # sem elas instaladas localmente o resto do site continua funcionando.
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    try:
        info = json.loads(bruto)
    except json.JSONDecodeError:
        # Aceita a chave em base64 também — mais à prova de erro de colagem
        # em campos de variável de ambiente que engasgam com texto grande
        # de várias linhas (o painel do Render, por exemplo).
        try:
            info = json.loads(base64.b64decode(bruto).decode("utf-8"))
        except Exception:
            raise ValueError(
                f"GOOGLE_SERVICE_ACCOUNT_JSON não é um JSON válido nem base64 válido "
                f"(recebi {len(bruto)} caractere(s) — confere se colou o conteúdo certo no Render)"
            )
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


# Casamento por nome tolerante: o "Salvar como" do navegador nomeia o
# arquivo pelo <title> de cada página, que vem diferente entre a página do
# evento e a de participantes/atletas (ex: "ADCC Brazil Open - Petrópolis -
# Smoothcomp.html" vs "Participants - ADCC Brazil Open - Petrópolis -
# Atletas.html") — bem diferente de "mesmo nome + sufixo" se o usuário não
# renomear na mão. Em vez de exigir isso, tira prefixo/sufixo de ruído
# comuns dos dois lados e casa pelo que sobra.
_PREFIXO_ATLETAS = re.compile(r"^participants\s*-\s*", re.I)
_SUFIXOS_RUIDO = re.compile(r"\s*-\s*(atletas|athletes|smoothcomp)\s*$", re.I)
_PALAVRAS_ATLETAS = re.compile(r"participants|atletas|athletes", re.I)


def _nome_normalizado(nome_arquivo):
    base = re.sub(r"\.html?$", "", nome_arquivo, flags=re.I)
    anterior = None
    while anterior != base:
        anterior = base
        base = _PREFIXO_ATLETAS.sub("", base)
        base = _SUFIXOS_RUIDO.sub("", base)
    return re.sub(r"\s+", " ", base).strip().lower()


def _eh_arquivo_atletas(nome_arquivo):
    return bool(_PALAVRAS_ATLETAS.search(nome_arquivo))


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
    grupos = {}
    for arquivo in arquivos:
        chave = _nome_normalizado(arquivo["name"])
        papel = "atletas" if _eh_arquivo_atletas(arquivo["name"]) else "evento"
        grupos.setdefault(chave, {})[papel] = arquivo

    for grupo in grupos.values():
        arquivo_evento = grupo.get("evento")
        arquivo_atletas = grupo.get("atletas")
        if arquivo_evento and not arquivo_atletas:
            log.append(f"{federacao} pendente: {arquivo_evento['name']} sem o arquivo de atletas ainda")
            continue
        if arquivo_atletas and not arquivo_evento:
            log.append(f"{federacao} pendente: {arquivo_atletas['name']} sem o arquivo do evento correspondente")
            continue
        _processar_par(drive, modulo, arquivo_evento, arquivo_atletas, origem_folder_id, destino_folder_id, log)


def verificar_e_importar():
    """Roda uma verificação completa (chamada pelo agendador diário, ou
    manualmente via admin). Nunca deixa uma exceção escapar — sempre volta
    uma lista de mensagens de log, mesmo em caso de erro (a chave mal
    configurada, biblioteca faltando, etc.), pra aparecer na tela do admin
    em vez de virar um erro 500 genérico."""
    try:
        drive = _cliente_drive()
    except Exception as exc:
        traceback.print_exc()
        return [f"Erro ao conectar no Google Drive: {exc}"]
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
