import os
import re
import shutil
import threading
import sys
import subprocess
import traceback
from datetime import datetime

# ──────────────────────────────────────────────
# ÍCONE NA BARRA DE TAREFAS DO WINDOWS
# Deve ficar ANTES de qualquer import de UI
# ──────────────────────────────────────────────
if sys.platform == "win32":
    import ctypes
    # AppUserModelID faz o Windows separar o app do python.exe na taskbar
    # e usar o ícone correto em vez do ícone do Python
    _APP_ID = "RNA.RenomeadorOrganizador.v2"
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:
        pass

# ──────────────────────────────────────────────
# SUPRIME JANELAS CMD PARA TODOS OS SUBPROCESSOS
# ──────────────────────────────────────────────
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

# ──────────────────────────────────────────────
# PASTA SEGURA PARA LOGS (sempre gravável)
# ──────────────────────────────────────────────
PASTA_LOGS = os.path.join(os.path.expanduser("~"), "Documents", "RNA_LOGS")

# ──────────────────────────────────────────────
# CAMINHOS DINÂMICOS (PyInstaller)
# ──────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR     = os.path.dirname(sys.executable)
    PATH_SUPORTE = os.path.join(BASE_DIR, "_internal", "bin")
else:
    BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
    PATH_SUPORTE = os.path.join(BASE_DIR, "bin")

PASTA_DESTINO_PADRAO = os.path.join(BASE_DIR, "Saida")
ICON_PATH = os.path.join(BASE_DIR, "rna_logo.ico")

# ── 1. BUSCA INTELIGENTE DO TESSERACT ──
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

from pdf2image import convert_from_path
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ── 2. BUSCA INTELIGENTE DO POPPLER ──
def _encontrar_poppler() -> str | None:
    candidatos = [
        os.path.join(PATH_SUPORTE, "Poppler", "poppler-25.12.0", "Library", "bin"),
        os.path.join(PATH_SUPORTE, "poppler", "Library", "bin"),
        os.path.join(BASE_DIR, "bin", "Poppler", "poppler-25.12.0", "Library", "bin"),
        r"C:\poppler-25.12.0\Library\bin",
        r"C:\poppler\Library\bin",
    ]
    for c in candidatos:
        if c and os.path.exists(os.path.join(c, "pdftoppm.exe")):
            return c
    return None

CAMINHO_POPPLER = _encontrar_poppler()

# ──────────────────────────────────────────────
# PALETA DE CORES
# ──────────────────────────────────────────────
C = {
    "bg":          "#0e0e10",
    "surface":     "#16161a",
    "surface2":    "#1e1e22",
    "border":      "#2a2a2e",
    "border_soft": "#222226",
    "gold":        "#c8b87a",
    "gold_dim":    "#a89050",
    "gold_text":   "#1a1800",
    "text_pri":    "#e8e6e0",
    "text_sec":    "#9a9890",
    "text_muted":  "#5a5a56",
    "log_bg":      "#0a0a0c",
}

# ──────────────────────────────────────────────
# WIDGET: CAMPO DE ENTRADA
# ──────────────────────────────────────────────
class CampoEntrada(ctk.CTkFrame):
    def __init__(self, master, label: str, placeholder: str = "",
                 valor_inicial: str = "", com_botao: bool = True,
                 is_date: bool = False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text=label.upper(),
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=C["text_muted"], width=90, anchor="w",
        ).grid(row=0, column=0, padx=(0, 12), sticky="w")

        self.entry = ctk.CTkEntry(
            self, placeholder_text=placeholder,
            font=ctk.CTkFont(
                family="Consolas" if is_date else "Segoe UI", size=12),
            fg_color=C["surface2"], border_color=C["border"], border_width=1,
            text_color=C["gold"] if is_date else C["text_sec"], height=36,
        )
        self.entry.grid(row=0, column=1, sticky="ew",
                        padx=(0, 10 if com_botao else 0))

        if valor_inicial:
            self.entry.insert(0, valor_inicial)

        if com_botao:
            ctk.CTkButton(
                self, text="Procurar", width=84, height=36,
                font=ctk.CTkFont(size=11),
                fg_color=C["surface2"], hover_color=C["surface"],
                border_color=C["border"], border_width=1,
                text_color=C["text_sec"], command=self._on_procurar,
            ).grid(row=0, column=2)

    def _on_procurar(self):
        pasta = filedialog.askdirectory()
        if pasta:
            self.entry.delete(0, "end")
            self.entry.insert(0, pasta)

    def get(self) -> str:
        return self.entry.get().strip()


# ──────────────────────────────────────────────
# WIDGET: LOG COLORIDO
# ──────────────────────────────────────────────
class LogBox(ctk.CTkFrame):

    CORES_TIPO = {
        "ok":   "#7aaa78",
        "warn": "#c8a84a",
        "err":  "#c07070",
        "info": "#6b9ec8",
        "ts":   "#3a3a38",
    }

    def __init__(self, master, **kwargs):
        super().__init__(
            master, fg_color=C["log_bg"],
            border_color=C["border_soft"], border_width=1,
            corner_radius=10, **kwargs,
        )
        import tkinter as tk
        self._text = tk.Text(
            self, background=C["log_bg"], foreground=C["text_muted"],
            font=("Consolas", 10), relief="flat", bd=0,
            padx=14, pady=10, state="disabled", wrap="word",
            insertbackground=C["gold"], selectbackground=C["surface2"],
        )
        self._text.pack(fill="both", expand=True, padx=1, pady=1)
        for nome, cor in self.CORES_TIPO.items():
            self._text.tag_configure(nome, foreground=cor)
        self._inserir("info", "Aguardando inicio...")

    def _inserir(self, tipo: str, msg: str):
        self._text.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.insert("end", f"[{ts}]  ", ("ts",))
        self._text.insert("end", f"{msg}\n", (tipo,))
        self._text.see("end")
        self._text.configure(state="disabled")

    def log(self, tipo: str, msg: str):
        self.after(0, lambda: self._inserir(tipo, msg))


# ──────────────────────────────────────────────
# WIDGET: LOGO (Canvas)
# ──────────────────────────────────────────────
class LogoCanvas(ctk.CTkCanvas):
    SZ = 40

    def __init__(self, master, **kwargs):
        super().__init__(
            master, width=self.SZ, height=self.SZ,
            bg=C["bg"], highlightthickness=0, **kwargs,
        )
        self._draw()

    def _draw(self):
        s = self.SZ; g = C["gold"]; g2 = C["gold_dim"]
        sf = C["surface2"]; bd = C["border"]
        r = 9
        pts = [
            4+r, 4,   s-4-r, 4,   s-4, 4,    s-4, 4+r,
            s-4, s-4-r,  s-4, s-4,  s-4-r, s-4,  4+r, s-4,
            4, s-4,  4, s-4-r,  4, 4+r,  4, 4,
        ]
        self.create_polygon(pts, smooth=True, fill=sf, outline=bd)
        self.create_rectangle(10, 10, 14, 30, fill=g,  outline="")
        self.create_rectangle(14, 10, 24, 14, fill=g,  outline="")
        self.create_rectangle(21, 14, 24, 20, fill=g,  outline="")
        self.create_rectangle(14, 19, 22, 22, fill=g2, outline="")
        self.create_line(21, 22, 29, 30, fill=g2, width=2.5, capstyle="round")


# ──────────────────────────────────────────────
# JANELA PRINCIPAL
# ──────────────────────────────────────────────
class ARNApp(ctk.CTk):

    APP_TITLE   = "RNA — Renomeador e Organizador"
    APP_VERSION = "v 2.5"
    WINDOW_SIZE = "620x560"

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=C["bg"])
        self.title(self.APP_TITLE)
        self.geometry(self.WINDOW_SIZE)
        self.resizable(False, False)
        self._set_icon()
        self._build_ui()

    def _set_icon(self):
        """
        Aplica ícone em três camadas:
          1. iconbitmap  → canto/título da janela
          2. iconphoto   → barra de tarefas ao rodar como .py
          3. AppUserModelID (no topo do arquivo) → separa do python.exe na taskbar
        """
        if not os.path.exists(ICON_PATH):
            return
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass
        try:
            import tkinter as tk
            img = tk.PhotoImage(file=ICON_PATH)
            self.iconphoto(True, img)
            self._icon_img = img  # evita garbage collection
        except Exception:
            pass

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=C["surface"],
                               corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        h_inner = ctk.CTkFrame(header, fg_color="transparent")
        h_inner.pack(fill="both", expand=True, padx=26, pady=15)

        LogoCanvas(h_inner).pack(side="left", padx=(0, 14))

        titles = ctk.CTkFrame(h_inner, fg_color="transparent")
        titles.pack(side="left", fill="y", expand=False)

        ctk.CTkLabel(
            titles, text="RNA — Renomeador e Organizador",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=C["text_pri"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            titles, text="PROCESSAMENTO DE DOCUMENTOS VIA OCR",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=C["text_muted"], anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            h_inner, text=self.APP_VERSION,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=C["text_muted"], fg_color=C["surface2"],
            corner_radius=4, padx=8, pady=3,
        ).pack(side="right")

        ctk.CTkFrame(self, fg_color=C["border"], height=1,
                     corner_radius=0).pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=26, pady=22)

        self.campo_origem = CampoEntrada(
            body, label="Origem", placeholder="Pasta com os PDFs...",
            valor_inicial=os.getcwd(),
        )
        self.campo_origem.pack(fill="x", pady=(0, 12))

        self.campo_destino = CampoEntrada(
            body, label="Destino", placeholder="Pasta de saida...",
            valor_inicial=PASTA_DESTINO_PADRAO,
        )
        self.campo_destino.pack(fill="x", pady=(0, 12))

        self.campo_data = CampoEntrada(
            body, label="Data", placeholder="DD.MM.AAAA",
            valor_inicial=datetime.now().strftime("%d.%m.%Y"),
            com_botao=False, is_date=True,
        )
        self.campo_data.pack(fill="x", pady=(0, 20))

        ctk.CTkFrame(body, fg_color=C["border_soft"],
                     height=1, corner_radius=0).pack(fill="x", pady=(0, 16))

        self.btn = ctk.CTkButton(
            body, text="INICIAR PROCESSAMENTO", height=48,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=C["gold"], hover_color=C["gold_dim"],
            text_color=C["gold_text"], corner_radius=10,
            command=self._iniciar_thread,
        )
        self.btn.pack(side="bottom", fill="x")

        self.log_box = LogBox(body)
        self.log_box.pack(side="top", fill="both", expand=True, pady=(0, 20))

    # ── Log helper ─────────────────────────────
    def log(self, mensagem: str):
        if any(mensagem.startswith(p) for p in ["✅", "🚚"]):
            tipo = "ok"
        elif mensagem.startswith("⚠️"):
            tipo = "warn"
        elif mensagem.startswith("❌"):
            tipo = "err"
        else:
            tipo = "info"
        limpa = mensagem.lstrip("✅🚚⚠️❌🔍ℹ️ ").strip()
        self.log_box.log(tipo, limpa)

    # ── OCR: extração ──────────────────────────
    @staticmethod
    def _extrair_dados(texto: str) -> tuple[str | None, str | None]:
        """
        Formatos do documento:
          Código : CÓDIGO REVENDEDOR 1.015.356
          Nome   : REVENDEDOR JOSEMIRA JANE DA SILVA CRISPIM
        """
        codigo = None
        cod_match = re.search(
            r"C[OÓ]DIGO\s+REVENDEDOR[\s:.\-]*([0-9][0-9.,\s]{3,15}[0-9])",
            texto,
            re.IGNORECASE,
        )
        if cod_match:
            apenas_digitos = re.sub(r"[^0-9]", "", cod_match.group(1))
            if 5 <= len(apenas_digitos) <= 12:
                codigo = apenas_digitos

        nome = None
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

        return codigo, nome

    @staticmethod
    def _nome_unico(pasta: str, nome_base: str) -> str:
        if not nome_base.lower().endswith(".pdf"):
            nome_base += ".pdf"
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

    def _iniciar_thread(self):
        self.btn.configure(state="disabled", text="PROCESSANDO...",
                           fg_color=C["surface2"])
        threading.Thread(target=self._processar, daemon=True).start()

    def _processar(self):
        if not CAMINHO_POPPLER:
            self.log("❌ Poppler nao encontrado no sistema.")
            self.after(0, lambda: messagebox.showerror(
                "Erro de Dependencia",
                "A pasta do Poppler nao foi encontrada.\nConsulte o guia de instalacao."
            ))
            self.after(0, self._restaurar_botao)
            return

        data_input         = self.campo_data.get()
        pasta_origem       = self.campo_origem.get()
        pasta_destino_base = self.campo_destino.get()

        try:
            datetime.strptime(data_input, "%d.%m.%Y")
        except ValueError:
            self.log("❌ Formato de data invalido. Use DD.MM.AAAA")
            self.after(0, lambda: messagebox.showerror(
                "Erro", "Use o formato DD.MM.AAAA\nEx: 21.02.2026"))
            self.after(0, self._restaurar_botao)
            return

        if not os.path.exists(pasta_origem):
            self.log(f"❌ Pasta de origem nao encontrada: {pasta_origem}")
            self.after(0, lambda: messagebox.showerror(
                "Erro", "Pasta de origem nao encontrada!"))
            self.after(0, self._restaurar_botao)
            return

        arquivos = [
            f for f in os.listdir(pasta_origem)
            if f.lower().endswith(".pdf") or f.startswith("Untitled_")
        ]

        if not arquivos:
            self.log("Nenhum arquivo encontrado na pasta de origem.")
            self.after(0, self._restaurar_botao)
            return

        # ── FASE 1: OCR e renomeação ────────────
        arquivos_prontos = []
        for arquivo in arquivos:
            self.log(f"🔍 Lendo: {arquivo}")
            caminho = os.path.join(pasta_origem, arquivo)
            try:
                paginas = convert_from_path(
                    caminho, poppler_path=CAMINHO_POPPLER,
                    first_page=1, last_page=1,
                )
                if not paginas:
                    self.log(f"⚠️ Nenhuma pagina convertida: {arquivo}")
                    continue

                texto = pytesseract.image_to_string(paginas[0], lang="por")
                if len(texto.strip()) < 20:
                    texto = pytesseract.image_to_string(paginas[0], lang="eng")

                cod, nome = self._extrair_dados(texto)

                if cod and nome:
                    nome_sugerido = re.sub(
                        r'[\\/*?:"<>|]', "",
                        f"{cod} - {nome}.pdf",
                    )
                    if arquivo.lower() == nome_sugerido.lower():
                        arquivos_prontos.append(arquivo)
                        continue
                    nome_final = self._nome_unico(pasta_origem, nome_sugerido)
                    os.rename(caminho, os.path.join(pasta_origem, nome_final))
                    arquivos_prontos.append(nome_final)
                    self.log(f"✅ Renomeado: {nome_final}")
                else:
                    self._salvar_dump_ocr(arquivo, texto)
                    motivo = []
                    if not cod:  motivo.append("codigo nao encontrado")
                    if not nome: motivo.append("nome nao encontrado")
                    self.log(
                        f"⚠️ Nao identificado ({', '.join(motivo)}): "
                        f"{arquivo} — dump em Documentos/RNA_LOGS/"
                    )

            except Exception as e:
                self.log(f"❌ Erro em '{arquivo}': {e}")
                self._salvar_log_erro(arquivo)

        # ── FASE 2: Mover ───────────────────────
        if not arquivos_prontos:
            self.log("Nenhum arquivo para mover.")
            self.after(0, self._restaurar_botao)
            return

        try:
            pasta_destino = os.path.join(pasta_destino_base, data_input)
            os.makedirs(pasta_destino, exist_ok=True)

            for arquivo in arquivos_prontos:
                origem  = os.path.join(pasta_origem, arquivo)
                destino = os.path.join(
                    pasta_destino,
                    self._nome_unico(pasta_destino, arquivo),
                )
                shutil.move(origem, destino)
                self.log(f"🚚 Enviado: {os.path.basename(destino)}")

            total = len(arquivos_prontos)
            self.after(0, lambda: messagebox.showinfo(
                "Concluido",
                f"Processo finalizado!\n{total} arquivo(s) organizado(s).",
            ))
        except Exception as e:
            self.log(f"❌ Erro ao mover arquivos: {e}")

        self.after(0, self._restaurar_botao)

    def _restaurar_botao(self):
        self.btn.configure(
            state="normal",
            text="INICIAR PROCESSAMENTO",
            fg_color=C["gold"],
        )


# ──────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = ARNApp()
    app.mainloop()