const API_KEY = "SUA_CHAVE_AQUI";
const GEMINI_ENDPOINT = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${API_KEY}`;

function processarPrint() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  // 1. Pega a URL ou o arquivo de imagem do Google Drive
  // Para este exemplo, vamos supor que o arquivo é o mais recente em uma pasta específica
  const folderId = "ID_DA_SUA_PASTA_COM_PRINTS"; 
  const folder = DriveApp.getFolderById(folderId);
  const files = folder.getFiles();
  
  if (!files.hasNext()) {
    Logger.log("Nenhum arquivo encontrado.");
    return;
  }
  
  const file = files.next(); // Pega o arquivo mais recente
  const blob = file.getBlob();
  const base64Data = Utilities.base64Encode(blob.getBytes());

  // 2. Monta o Prompt para a IA
  const prompt = "Extraia os dados desta imagem e retorne APENAS um JSON no formato: " +
                 "{ 'data': 'DD/MM/AAAA', 'valor': 0.00, 'descricao': 'texto', 'categoria': 'texto' }. " +
                 "Não escreva nada além do JSON.";

  const payload = {
    "contents": [{
      "parts": [
        {"text": prompt},
        {
          "inline_data": {
            "mime_type": "image/jpeg",
            "data": base64Data
          }
        }
      ]
    }]
  };

  // 3. Faz a requisição para o Gemini
  const options = {
    "method": "post",
    "contentType": "application/json",
    "payload": JSON.stringify(payload)
  };

  const response = UrlFetchApp.fetch(GEMINI_ENDPOINT, options);
  const jsonResponse = JSON.parse(response.getContentText());
  const aiText = jsonResponse.candidates[0].content.parts[0].text;
  
  // Limpa possíveis marcações de Markdown do JSON
  const cleanJson = aiText.replace(/```json|```/g, "");
  const dados = JSON.parse(cleanJson);

  // 4. Insere na última linha da planilha
  sheet.appendRow([dados.data, dados.descricao, dados.categoria, dados.valor]);
  
  Logger.log("Dados inseridos com sucesso!");
}