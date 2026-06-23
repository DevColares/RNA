// Aguarda o pywebview carregar
window.addEventListener('pywebviewready', async function() {
    console.log("PyWebView carregado com sucesso.");

    const inputOrigem = document.getElementById('inputOrigem');
    if (window.pywebview && pywebview.api.obter_pasta_atual) {
        inputOrigem.value = await pywebview.api.obter_pasta_atual();
    }
    
    const inputDestino = document.getElementById('inputDestino');
    if(inputOrigem.value) {
        inputDestino.value = inputOrigem.value + "\\Saida";
    }
});

// Modal de Configurações
function abrirConfiguracoes() {
    document.getElementById('modalConfig').classList.remove('hidden');
}

function fecharConfiguracoes() {
    document.getElementById('modalConfig').classList.add('hidden');
}

// Alternar tema
function toggleTheme() {
    const body = document.body;
    if (body.classList.contains('theme-dark')) {
        body.classList.remove('theme-dark');
        body.classList.add('theme-light');
    } else {
        body.classList.remove('theme-light');
        body.classList.add('theme-dark');
    }
}

// Dialog de seleção de pasta nativo
async function procurarPasta(inputId) {
    if (!window.pywebview) return;
    const caminho = await pywebview.api.escolher_pasta();
    if (caminho && caminho.length > 0) {
        document.getElementById(inputId).value = caminho;
    }
}

let pollInterval;

// Iniciar Processamento
async function iniciar() {
    const origem = document.getElementById('inputOrigem').value;
    const destino = document.getElementById('inputDestino').value;

    // Coletar configurações do modal
    const config = {
        tipoArquivo: document.getElementById('configTipoArquivo').value,
        palavraInicial: document.getElementById('configPalavraInicial').value
    };
    
    const btn = document.getElementById('btnIniciar');
    btn.disabled = true;
    btn.innerText = "PROCESSANDO...";
    
    if (window.pywebview) {
        // Limpa logs
        document.getElementById('logBox').innerHTML = '';
        adicionarLog('info', 'Iniciando processamento...');
        
        // Dispara em background
        await pywebview.api.iniciar_processamento(origem, destino, config);
        
        // Inicia polling para evitar erro de Thread no PyWebView
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(pollUpdates, 500);
    }
}

async function pollUpdates() {
    if (!window.pywebview) return;
    try {
        const updates = await pywebview.api.get_updates();
        
        if (updates.logs && updates.logs.length > 0) {
            updates.logs.forEach(log => {
                adicionarLog(log.tipo, log.msg);
            });
        }
        
        if (updates.is_done) {
            clearInterval(pollInterval);
            processamentoConcluido(updates.done_success, updates.done_msg, updates.failed_files);
        }
    } catch(e) {
        console.error("Erro no polling", e);
    }
}

function adicionarLog(tipo, mensagem) {
    const logBox = document.getElementById('logBox');
    
    const agora = new Date();
    const h = String(agora.getHours()).padStart(2, '0');
    const m = String(agora.getMinutes()).padStart(2, '0');
    const s = String(agora.getSeconds()).padStart(2, '0');
    const timestamp = `[${h}:${m}:${s}]`;
    
    const linha = document.createElement('div');
    linha.className = 'log-linha';
    
    const spanTs = document.createElement('span');
    spanTs.className = 'log-ts';
    spanTs.innerText = timestamp;
    
    const spanMsg = document.createElement('span');
    spanMsg.className = `log-${tipo}`;
    spanMsg.innerText = mensagem;
    
    linha.appendChild(spanTs);
    linha.appendChild(spanMsg);
    
    logBox.appendChild(linha);
    logBox.scrollTop = logBox.scrollHeight;
}

function processamentoConcluido(sucesso, mensagem, failed_files) {
    const btn = document.getElementById('btnIniciar');
    btn.disabled = false;
    btn.innerText = "INICIAR PROCESSAMENTO";
    
    if (sucesso) {
        adicionarLog('ok', '=== ' + mensagem + ' ===');
    } else {
        adicionarLog('err', '=== Falha: ' + mensagem + ' ===');
    }

    if (failed_files && failed_files.length > 0) {
        // Exibe modal de confirmação estilizado
        document.getElementById('confirmMensagem').innerText = mensagem;
        document.getElementById('confirmPergunta').innerText = `${failed_files.length} arquivo(s) não puderam ser lidos. Deseja renomeá-los manualmente?`;
        document.getElementById('modalConfirm').classList.remove('hidden');
        // Guarda os arquivos para usar no callback
        window._pendingFailedFiles = failed_files;
    }
}

let arquivosComErroGlobais = [];
let indiceManualAtual = 0;
let dadosManuaisColetados = [];

function resolverConfirm(sim) {
    document.getElementById('modalConfirm').classList.add('hidden');
    if (sim) {
        abrirModalManual(window._pendingFailedFiles || []);
    }
    window._pendingFailedFiles = null;
}

async function abrirModalManual(files) {
    arquivosComErroGlobais = files;
    indiceManualAtual = 0;
    dadosManuaisColetados = [];
    
    document.getElementById('modalManual').classList.remove('hidden');
    await carregarArquivoManualAtual();
}

async function carregarArquivoManualAtual() {
    if (indiceManualAtual >= arquivosComErroGlobais.length) {
        finalizarColetaManual();
        return;
    }
    
    const arquivo = arquivosComErroGlobais[indiceManualAtual];
    document.getElementById('manualNomeArquivo').innerText = `Arquivo ${indiceManualAtual + 1} de ${arquivosComErroGlobais.length}: ${arquivo}`;
    
    document.getElementById('manual_cod').value = '';
    document.getElementById('manual_nome').value = '';
    document.getElementById('manual_data').value = '';
    
    const imgEl = document.getElementById('manualPreviewImg');
    const loadEl = document.getElementById('manualPreviewLoading');
    
    imgEl.style.display = 'none';
    imgEl.src = '';
    loadEl.style.display = 'block';
    loadEl.innerText = "Carregando visualização...";
    
    const btnSalvar = document.getElementById('btnSalvarManual');
    if (indiceManualAtual === arquivosComErroGlobais.length - 1) {
        btnSalvar.innerText = "Concluir e Processar";
    } else {
        btnSalvar.innerText = "Próximo Arquivo";
    }
    
    const origem = document.getElementById('inputOrigem').value;
    const base64Img = await pywebview.api.obter_preview_arquivo(origem, arquivo);
    
    if (base64Img) {
        imgEl.src = base64Img;
        imgEl.style.display = 'block';
        loadEl.style.display = 'none';
    } else {
        loadEl.innerText = "Não foi possível carregar o preview para este arquivo.";
    }
}

function pularArquivoManual() {
    indiceManualAtual++;
    carregarArquivoManualAtual();
}

function salvarAtualEProximo() {
    const cod = document.getElementById('manual_cod').value.trim();
    const nome = document.getElementById('manual_nome').value.trim();
    const data = document.getElementById('manual_data').value.trim();
    
    if (!cod || !nome || !data) {
        alert("Por favor, preencha todos os campos ou clique em 'Pular' se não quiser renomear este arquivo.");
        return;
    }
    
    dadosManuaisColetados.push({
        arquivo_original: arquivosComErroGlobais[indiceManualAtual],
        cod: cod,
        nome: nome,
        data: data
    });
    
    indiceManualAtual++;
    carregarArquivoManualAtual();
}

async function finalizarColetaManual() {
    document.getElementById('modalManual').classList.add('hidden');
    
    if (dadosManuaisColetados.length === 0) {
        adicionarLog('warn', 'Nenhum arquivo foi renomeado manualmente.');
        return;
    }
    
    const origem = document.getElementById('inputOrigem').value;
    const destino = document.getElementById('inputDestino').value;
    
    const btn = document.getElementById('btnIniciar');
    btn.disabled = true;
    btn.innerText = "PROCESSANDO...";
    
    if (window.pywebview) {
        document.getElementById('logBox').innerHTML = '';
        adicionarLog('info', 'Iniciando processamento manual...');
        
        await pywebview.api.iniciar_processamento_manual(origem, destino, dadosManuaisColetados);
        
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(pollUpdates, 500);
    }
}
