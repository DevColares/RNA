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
            processamentoConcluido(updates.done_success, updates.done_msg);
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

function processamentoConcluido(sucesso, mensagem) {
    const btn = document.getElementById('btnIniciar');
    btn.disabled = false;
    btn.innerText = "INICIAR PROCESSAMENTO";
    
    if(sucesso) {
        adicionarLog('ok', '=== ' + mensagem + ' ===');
        alert(mensagem);
    } else {
        adicionarLog('err', '=== Falha: ' + mensagem + ' ===');
        alert("Erro: " + mensagem);
    }
}
