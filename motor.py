import os
import re
import shutil
import traceback
import sys
import subprocess
from datetime import datetime
from pdf2image import convert_from_path

# ──────────────────────────────────────────────
# PASTA SEGURA PARA LOGS (sempre gravável)
# ──────────────────────────────────────────────
PASTA_LOGS = os.path.join(os.path.expanduser("~"), "Documents", "RNA_LOGS")

if sys.platform == "win32":
    _Popen_original = subprocess.Popen

    class _PopenSemJanela(_Popen_original):
        def __init__(self, *args, **kwargs):
            si = subprocess.STARTUPINFO()
            si.dwFlags    |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            kwargs.setdefault("startupinfo", si)
            kwargs.setdefault("creationflags", 0)
            kwargs["creationflags"] |= subprocess.CREATE_NO_WINDOW
            if kwargs.get("stdin") is None:
                kwargs["stdin"] = subprocess.PIPE
            super().__init__(*args, **kwargs)

    subprocess.Popen = _PopenSemJanela  # type: ignore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PATH_SUPORTE = os.path.join(BASE_DIR, "Projeto_RNA", "bin")

def _encontrar_tesseract():
    candidatos = [
        os.path.join(PATH_SUPORTE, "Tesseract"),
        os.path.join(PATH_SUPORTE, "tesseract"),
        r"C:\Program Files\Tesseract-OCR",
        r"C:\Program Files (x86)\Tesseract-OCR",
    ]
    for d in candidatos:
        cmd  = os.path.join(d, "tesseract.exe")
        data = os.path.join(d, "tessdata")
        if os.path.exists(cmd):
            return cmd, data
    return (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tessdata",
    )

TESS_CMD, TESS_DATA = _encontrar_tesseract()
os.environ["TESSDATA_PREFIX"] = TESS_DATA

import pytesseract
pytesseract.pytesseract.tesseract_cmd = TESS_CMD

if sys.platform == "win32":
    _si = subprocess.STARTUPINFO()
    _si.dwFlags    |= subprocess.STARTF_USESHOWWINDOW
    _si.wShowWindow = subprocess.SW_HIDE
    pytesseract.pytesseract.subprocess_args = lambda include_stdout=True: dict(
        startupinfo=_si,
        creationflags=subprocess.CREATE_NO_WINDOW,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )

def _encontrar_poppler() -> str | None:
    candidatos = [
        os.path.join(PATH_SUPORTE, "Poppler", "poppler-25.12.0", "Library", "bin"),
        os.path.join(PATH_SUPORTE, "poppler", "Library", "bin"),
        os.path.join(BASE_DIR, "Projeto_RNA", "bin", "Poppler", "poppler-25.12.0", "Library", "bin"),
        r"C:\poppler-25.12.0\Library\bin",
        r"C:\poppler\Library\bin",
    ]
    for c in candidatos:
        if c and os.path.exists(os.path.join(c, "pdftoppm.exe")):
            return c
    return None

CAMINHO_POPPLER = _encontrar_poppler()


class MotorRNA:
    def __init__(self):
        pass

    @staticmethod
    def _extrair_dados(texto: str):
        codigo = None
        nome = None
        data_pedido = None # <-- Nova variável para a data
        
        # 1. Extrair Código
        cod_match = re.search(
            r"C[OÓ]DIGO\s+REVENDEDOR[\s:.\-]*([0-9][0-9.,\s]{3,15}[0-9])",
            texto,
            re.IGNORECASE,
        )
        if cod_match:
            apenas_digitos = re.sub(r"[^0-9]", "", cod_match.group(1))
            if 5 <= len(apenas_digitos) <= 12:
                codigo = apenas_digitos

        # 2. Extrair Nome
        for match in re.finditer(
            r"(?<!DIGO\s)(?<!DIGO)REVENDEDOR[\s:.\-]+([A-ZÀ-Úa-zà-ú][^\n]{2,60})",
            texto,
            re.IGNORECASE,
        ):
            candidato = match.group(1).strip()
            candidato = re.sub(r'[\s,.\-]+$', '', candidato)
            if len(candidato) >= 3 and not candidato.isdigit():
                nome = candidato
                break

        # 3. Extrair Data — tenta "DATA DO EXTRATO" primeiro
        data_match = re.search(
            r"DATA DO EXTRATO[\s\S]*?([0-9]{2}/[0-9]{2}/[0-9]{4})",
            texto,
            re.IGNORECASE
        )
        # Fallback: Online dd/mm/aaaa
        if not data_match:
            data_match = re.search(
                r"Online\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
                texto,
                re.IGNORECASE
            )
        # Fallback: Presencial dd/mm/aaaa
        if not data_match:
            data_match = re.search(
                r"Presencial\s*([0-9]{2}/[0-9]{2}/[0-9]{4})",
                texto,
                re.IGNORECASE
            )
        if data_match:
            data_pedido = data_match.group(1)

        return codigo, nome, data_pedido

    @staticmethod
    def _nome_unico(pasta: str, nome_base: str) -> str:
        nome_puro, ext = os.path.splitext(nome_base)
        nome_final = nome_base
        contador   = 2
        while os.path.exists(os.path.join(pasta, nome_final)):
            nome_final = f"{nome_puro} ({contador}){ext}"
            contador  += 1
        return nome_final

    @staticmethod
    def _salvar_dump_ocr(arquivo: str, texto: str):
        try:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            nome_dump = os.path.splitext(arquivo)[0] + "_ocr.txt"
            caminho   = os.path.join(PASTA_LOGS, nome_dump)
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(f"=== OCR DUMP: {arquivo} ===\n")
                f.write(f"=== {datetime.now()} ===\n\n")
                f.write(texto)
        except Exception:
            pass

    @staticmethod
    def _salvar_log_erro(arquivo: str):
        try:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            caminho_log = os.path.join(PASTA_LOGS, "LOG_DE_ERRO.txt")
            with open(caminho_log, "a", encoding="utf-8") as f:
                f.write(f"\n--- Erro no arquivo: {arquivo} ---\n")
                f.write(traceback.format_exc())
        except Exception:
            pass

    def processar(self, pasta_origem: str, pasta_destino_base: str, config: dict, on_log, on_done):

        inicio_processamento = datetime.now()

        tipo_arquivo = config.get("tipoArquivo", ".pdf").lower()
        palavra_inicial = config.get("palavraInicial", "").strip()

        def emit_log(msg):
            if any(msg.startswith(p) for p in ["✅", "🚚"]):
                tipo = "ok"
            elif msg.startswith("⚠️"):
                tipo = "warn"
            elif msg.startswith("❌"):
                tipo = "err"
            else:
                tipo = "info"
            limpa = msg.lstrip("✅🚚⚠️❌🔍ℹ️ ").strip()
            on_log(tipo, limpa)

        if tipo_arquivo == ".pdf" and not CAMINHO_POPPLER:
            emit_log("❌ Poppler nao encontrado no sistema.")
            on_done(False, "A pasta do Poppler não foi encontrada.")
            return

        if not os.path.exists(pasta_origem):
            emit_log(f"❌ Pasta de origem nao encontrada: {pasta_origem}")
            on_done(False, "Pasta de origem não encontrada!")
            return

        arquivos = []
        arquivos_com_erro = []
        for f in os.listdir(pasta_origem):
            if not f.lower().endswith(tipo_arquivo):
                continue
            if palavra_inicial and not f.lower().startswith(palavra_inicial.lower()):
                continue
            arquivos.append(f)

        if not arquivos:
            emit_log(f"Nenhum arquivo '{tipo_arquivo}' encontrado na pasta de origem.")
            on_done(True, f"Nenhum arquivo {tipo_arquivo} para processar.")
            return

        # FASE 1: OCR, renomeação e extração da data
        arquivos_prontos = []  # Guarda dicionários com nome e data
        for arquivo in arquivos:
            emit_log(f"🔍 Lendo: {arquivo}")
            caminho = os.path.join(pasta_origem, arquivo)
            try:
                if tipo_arquivo == ".pdf":
                    paginas = convert_from_path(
                        caminho, poppler_path=CAMINHO_POPPLER,
                        first_page=1, last_page=1,
                    )
                    if not paginas:
                        emit_log(f"⚠️ Nenhuma pagina convertida: {arquivo}")
                        continue
                    imagem_ocr = paginas[0]
                else:
                    from PIL import Image
                    imagem_ocr = Image.open(caminho)

                texto = pytesseract.image_to_string(imagem_ocr, lang="por")
                if len(texto.strip()) < 20:
                    texto = pytesseract.image_to_string(imagem_ocr, lang="eng")

                # Recebe os 3 dados agora!
                cod, nome, data_pedido = self._extrair_dados(texto)

                if cod and nome and data_pedido:
                    nome_sugerido = re.sub(
                        r'[\\/*?:"<>|]', "",
                        f"{cod} - {nome}{tipo_arquivo}"
                    )

                    # Substitui barras por pontos para criar pasta no Windows (Ex: 15/05/2026 -> 15.05.2026)
                    data_formatada = data_pedido.replace("/", ".")

                    if arquivo.lower() == nome_sugerido.lower():
                        arquivos_prontos.append({"nome": arquivo, "data": data_formatada})
                        continue

                    nome_final = self._nome_unico(pasta_origem, nome_sugerido)
                    os.rename(caminho, os.path.join(pasta_origem, nome_final))

                    # Guarda o nome final e a data encontrada no OCR
                    arquivos_prontos.append({"nome": nome_final, "data": data_formatada})
                    emit_log(f"✅ Renomeado: {nome_final}")
                else:
                    self._salvar_dump_ocr(arquivo, texto)
                    motivo = []
                    if not cod: motivo.append("código")
                    if not nome: motivo.append("nome")
                    if not data_pedido: motivo.append("data do pedido")
                    emit_log(
                        f"⚠️ Faltando ({', '.join(motivo)}): "
                        f"{arquivo} — dump salvo"
                    )
                    arquivos_com_erro.append(arquivo)

            except Exception as e:
                emit_log(f"❌ Erro em '{arquivo}': {e}")
                self._salvar_log_erro(arquivo)
                arquivos_com_erro.append(arquivo)

        # FASE 2: Mover
        if not arquivos_prontos:
            emit_log("Nenhum arquivo processado completamente para mover.")
            on_done(True, "Processo finalizado.", arquivos_com_erro)
            return

        try:
            for item in arquivos_prontos:
                arquivo_nome = item["nome"]
                arquivo_data = item["data"]  # Data do OCR (ex: 15.05.2026)

                origem = os.path.join(pasta_origem, arquivo_nome)

                # Cria a pasta respectiva da data lida no PDF
                pasta_destino = os.path.join(pasta_destino_base, arquivo_data)
                os.makedirs(pasta_destino, exist_ok=True)

                destino = os.path.join(
                    pasta_destino,
                    self._nome_unico(pasta_destino, arquivo_nome),
                )
                shutil.move(origem, destino)
                emit_log(f"🚚 Enviado: {os.path.basename(destino)} -> pasta {arquivo_data}/")

            total = len(arquivos_prontos)

            tempo_decorrido = datetime.now() - inicio_processamento
            minutos = int(tempo_decorrido.total_seconds() // 60)
            segundos = int(tempo_decorrido.total_seconds() % 60)
            tempo_str = f"{minutos}m {segundos}s" if minutos > 0 else f"{segundos}s"

            on_done(True, f"Processo finalizado em {tempo_str}! {total} arquivo(s) organizado(s) em pastas por data.", arquivos_com_erro)
        except Exception as e:
            emit_log(f"❌ Erro ao mover arquivos: {e}")
            on_done(False, f"Erro ao mover: {e}", arquivos_com_erro)

    def processar_manual(self, pasta_origem: str, pasta_destino_base: str, dados_manuais: list, on_log, on_done):
        def emit_log(msg):
            if any(msg.startswith(p) for p in ["✅", "🚚"]):
                tipo = "ok"
            elif msg.startswith("⚠️"):
                tipo = "warn"
            elif msg.startswith("❌"):
                tipo = "err"
            else:
                tipo = "info"
            limpa = msg.lstrip("✅🚚⚠️❌🔍ℹ️ ").strip()
            on_log(tipo, limpa)

        emit_log("ℹ️ Iniciando renomeação manual...")
        arquivos_prontos = []

        for item in dados_manuais:
            arquivo = item.get("arquivo_original")
            cod = item.get("cod")
            nome = item.get("nome")
            data_faturamento = item.get("data")

            caminho_origem = os.path.join(pasta_origem, arquivo)
            if not os.path.exists(caminho_origem):
                emit_log(f"❌ Arquivo não encontrado: {arquivo}")
                continue

            # Extensão
            _, ext = os.path.splitext(arquivo)
            
            nome_sugerido = re.sub(
                r'[\\/*?:"<>|]', "",
                f"{cod} - {nome}{ext}"
            )

            data_formatada = data_faturamento.replace("/", ".")
            
            try:
                if arquivo.lower() == nome_sugerido.lower():
                    arquivos_prontos.append({"nome": arquivo, "data": data_formatada})
                else:
                    nome_final = self._nome_unico(pasta_origem, nome_sugerido)
                    os.rename(caminho_origem, os.path.join(pasta_origem, nome_final))
                    arquivos_prontos.append({"nome": nome_final, "data": data_formatada})
                    emit_log(f"✅ Renomeado (Manual): {nome_final}")
            except Exception as e:
                emit_log(f"❌ Erro ao renomear '{arquivo}': {e}")
        
        # Mover
        for item in arquivos_prontos:
            arquivo_nome = item["nome"]
            arquivo_data = item["data"]

            origem = os.path.join(pasta_origem, arquivo_nome)
            pasta_destino = os.path.join(pasta_destino_base, arquivo_data)
            os.makedirs(pasta_destino, exist_ok=True)

            destino = os.path.join(
                pasta_destino,
                self._nome_unico(pasta_destino, arquivo_nome),
            )
            try:
                shutil.move(origem, destino)
                emit_log(f"🚚 Enviado: {os.path.basename(destino)} -> pasta {arquivo_data}/")
            except Exception as e:
                emit_log(f"❌ Erro ao mover '{arquivo_nome}': {e}")

        on_done(True, "Renomeação manual finalizada!")