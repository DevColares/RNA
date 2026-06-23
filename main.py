import webview
import os
import threading
from motor import MotorRNA

class Api:
    def __init__(self):
        self._window = None
        self._motor = MotorRNA()
        self._logs = []
        self._is_done = False
        self._done_success = False
        self._done_msg = ""
        self._done_failed_files = []
        
    def set_window(self, window):
        self._window = window

    def minimizar(self):
        if self._window:
            self._window.minimize()

    def maximizar(self):
        if self._window:
            self._window.toggle_fullscreen()

    def fechar(self):
        if self._window:
            self._window.destroy()
            
    def escolher_pasta(self):
        """Abre o diálogo nativo para seleção de pastas e retorna o caminho."""
        if self._window:
            # Tenta usar a interface nova do pywebview 6.x ou cai para o legado
            dialog_type = getattr(webview, 'OPEN_DIALOG', 1) # fallback
            if hasattr(webview, 'FileDialog'):
                dialog_type = webview.FileDialog.FOLDER
            elif hasattr(webview, 'FOLDER_DIALOG'):
                dialog_type = webview.FOLDER_DIALOG
                
            result = self._window.create_file_dialog(dialog_type)
            if result and len(result) > 0:
                return result[0]
        return ""
        

        
    def obter_pasta_atual(self):
        return os.getcwd()
        
    def get_updates(self):
        """Chamado pelo frontend para buscar novos logs (Polling) evitando erros de Thread."""
        updates = {
            "logs": self._logs.copy(),
            "is_done": self._is_done,
            "done_success": self._done_success,
            "done_msg": self._done_msg,
            "failed_files": self._done_failed_files.copy()
        }
        self._logs.clear()
        if self._is_done:
            self._is_done = False
            self._done_failed_files.clear()
        return updates
        
    def iniciar_processamento(self, origem, destino, config):
        """Roda o processamento em background recebendo as configurações."""
        self._logs.clear()
        self._is_done = False
        threading.Thread(target=self._run_engine, args=(origem, destino, config), daemon=True).start()
    
    def _run_engine(self, origem, destino, config):
        def on_log(tipo, msg):
            self._logs.append({"tipo": tipo, "msg": msg})

        def on_done(sucesso, msg, failed_files=None):
            self._done_success = sucesso
            self._done_msg = msg
            self._done_failed_files = failed_files or []
            self._is_done = True

        self._motor.processar(origem, destino, config, on_log, on_done)

    def iniciar_processamento_manual(self, origem, destino, dados_manuais):
        """Roda a renomeação manual em background."""
        self._logs.clear()
        self._is_done = False
        threading.Thread(target=self._run_engine_manual, args=(origem, destino, dados_manuais), daemon=True).start()

    def _run_engine_manual(self, origem, destino, dados_manuais):
        def on_log(tipo, msg):
            self._logs.append({"tipo": tipo, "msg": msg})

        def on_done(sucesso, msg):
            self._done_success = sucesso
            self._done_msg = msg
            self._done_failed_files = []
            self._is_done = True

        self._motor.processar_manual(origem, destino, dados_manuais, on_log, on_done)

    def obter_preview_arquivo(self, origem, arquivo):
        """Gera uma imagem base64 do cabeçalho do arquivo para exibição no frontend."""
        import base64
        from io import BytesIO
        caminho = os.path.join(origem, arquivo)
        if not os.path.exists(caminho):
            return ""

        try:
            if arquivo.lower().endswith('.pdf'):
                from pdf2image import convert_from_path
                from motor import CAMINHO_POPPLER
                paginas = convert_from_path(caminho, poppler_path=CAMINHO_POPPLER, first_page=1, last_page=1)
                if not paginas: return ""
                img = paginas[0]
            else:
                from PIL import Image
                img = Image.open(caminho)

            # Cortar a parte superior (cabeçalho) - 35% da imagem
            width, height = img.size
            crop_height = min(height, int(height * 0.35))
            img_cropped = img.crop((0, 0, width, crop_height))

            buffered = BytesIO()
            img_cropped.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            return f"data:image/png;base64,{img_str}"
        except Exception as e:
            print(f"Erro ao gerar preview: {e}")
            return ""

if __name__ == '__main__':
    api = Api()
    
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ui', 'index.html')
    
    window = webview.create_window(
        'RNA - Renomeador e Organizador', 
        url=html_path, 
        js_api=api,
        width=700, 
        height=650,
        background_color='#0F172A'
        # Removemos frameless=True e easy_drag=False para usar a janela padrao do Windows
    )
    
    api.set_window(window)
    
    webview.start(http_server=True)
