# ZTelegramDownloader / Telegram Media Downloader & On-Fly Scoper

Esta ferramenta em Python foi desenvolvida para baixar mídias (fotos e documentos) de um canal ou chat específico do Telegram. 

Ela possui a capacidade de buscar mensagens históricas e monitorar continuamente por novas mensagens.

Um recurso chave é o modo `--onfly`, que permite processar arquivos de documento grandes de forma eficiente em termos de memória, extraindo apenas linhas que correspondem a um padrão predefinido, sem a necessidade de baixar ou armazenar o arquivo inteiro.

## Funcionalidades

*   **Download Histórico:** Baixa mídias de todas as mensagens anteriores no canal/chat especificado.
*   **Monitoramento Contínuo:** Verifica periodicamente por novas mensagens e baixa/processa suas mídias.
*   **Histórico de Downloads:** Mantém um registro (`downloaded_history.txt`) dos arquivos já processados para evitar duplicidade.
*   **Modo `--onfly` para Economia de Memória:**
    *   Quando ativado e combinado com um escopo de domínios/palavras-chave, processa arquivos de documento *em tempo real* (streaming).
    *   Lê o arquivo linha por linha diretamente do Telegram.
    *   Se uma linha contiver algum dos domínios/palavras-chave do escopo, ela é salva em um arquivo `{nome_original}_scope.txt`.
    *   O arquivo original completo **não é baixado** se o modo `--onfly` estiver ativo e pelo menos uma correspondência de escopo for encontrada, economizando significativamente memória e espaço em disco para arquivos grandes.
*   **Filtro de Escopo:** Permite especificar domínios ou palavras-chave (via argumento ou arquivo) para focar o processamento do modo `--onfly`.
*   **Autenticação Interativa:** Guia o usuário pelo processo de login, incluindo códigos e senha 2FA, se necessário.

## Configuração

Antes de executar o script, você **precisa** configurar as seguintes variáveis no início do arquivo `.py`:

1.  `API_ID`: Seu ID de API do Telegram. Obtenha em [my.telegram.org](https://my.telegram.org/apps).
2.  `API_HASH`: Seu Hash de API do Telegram. Obtenha junto com o `API_ID`.
3.  `PHONE_NUMBER`: Seu número de telefone associado à conta Telegram (formato internacional, ex: `+5511999999999`).
4.  `TARGET_CHANNEL_INPUT`: O ID numérico (ex: `-1001234567890`) ou o username (ex: `'nomedocanal'`) do canal ou chat alvo.

Outras configurações (opcionais, com valores padrão):
*   `DOWNLOAD_FOLDER`: Pasta onde os arquivos serão salvos (padrão: `downloads`).
*   `HISTORY_FILE`: Arquivo para rastrear IDs de mensagens processadas (padrão: `downloaded_history.txt`).
*   `SESSION_NAME`: Nome do arquivo de sessão do Telethon (padrão: `my_telegram_session`).
*   `CHECK_INTERVAL_SECONDS`: Intervalo em segundos para verificar novas mensagens no modo de monitoramento (padrão: `300`).
*   `MESSAGES_FETCH_LIMIT_MONITORING`: Quantidade de mensagens recentes a verificar em cada ciclo de monitoramento (padrão: `50`).
*   `MESSAGES_FETCH_LIMIT_HISTORICAL`: Quantidade de mensagens a buscar por lote na varredura histórica (padrão: `200`).

## Dependências

*   Python 3.7+
*   Telethon

## Instalação

1.  Clone este repositório (ou baixe o script).
2.  Instale a dependência:
    ```bash
    pip install telethon
    ```
3.  Configure as variáveis `API_ID`, `API_HASH`, `PHONE_NUMBER`, e `TARGET_CHANNEL_INPUT` no script.

## Uso

Execute o script a partir do terminal:

```bash
python seu_script.py [opções]
```

**Opções de Linha de Comando:**

*   `--onfly`: Ativa o processamento "on-the-fly". Se domínios de escopo forem fornecidos, apenas as linhas correspondentes de documentos serão salvas em um arquivo `_scope.txt`, e o arquivo original não será baixado (se houver correspondências).
*   `-s, --scope DOMINIOS`: Lista de domínios/palavras-chave separados por vírgula para filtrar no modo `--onfly` (ex: `example.com,test.org,palavra_chave`). A busca é case-insensitive.
*   `-sf, --scope-file CAMINHO_ARQUIVO`: Caminho para um arquivo de texto contendo um domínio/palavra-chave por linha para filtrar no modo `--onfly`. Linhas começando com `#` são ignoradas.

**Exemplos:**

1.  **Baixar tudo (histórico e monitorar), sem modo on-fly:**
    ```bash
    python seu_script.py
    ```

2.  **Ativar modo on-fly com escopo definido por string:**
    *   Irá processar documentos e, se encontrar linhas com `meusite.com` ou `outrodominio.net`, salvará essas linhas em `nome_do_arquivo_scope.txt`.
    *   Fotos serão baixadas normalmente.
    *   Documentos que não contenham o escopo não terão um arquivo `_scope.txt` gerado e não serão baixados.
    ```bash
    python seu_script.py --onfly -s meusite.com,outrodominio.net
    ```

3.  **Ativar modo on-fly com escopo definido por arquivo:**
    ```bash
    python seu_script.py --onfly -sf lista_de_dominios.txt
    ```
    Onde `lista_de_dominios.txt` poderia conter:
    ```
    # Domínios de interesse
    site1.com
    palavraimportante
    subdominio.site2.org
    ```

4.  **Baixar tudo, mas se o modo on-fly *estivesse* ativo, usaria este escopo (apenas para ilustrar que o escopo pode ser fornecido sem `--onfly`, mas não terá o efeito de economia de memória):**
    *   Neste caso, o script baixará os arquivos completos. O aviso sobre "Domínios de escopo fornecidos, mas --onfly NÃO está ativo" será exibido.
    ```bash
    python seu_script.py -s example.com
    ```

### O Parâmetro `--onfly` Detalhado

O principal objetivo do parâmetro `--onfly` é **economizar memória e espaço em disco** ao lidar com arquivos de documento potencialmente grandes (como logs, dumps de texto, etc.).

Como funciona:
1.  Quando `--onfly` é ativado e um escopo de busca (domínios/palavras-chave) é fornecido:
2.  O script **não baixa o arquivo de documento inteiro** para a memória RAM ou para o disco inicialmente.
3.  Em vez disso, ele solicita o arquivo do Telegram em *chunks* (pedaços pequenos).
4.  Cada *chunk* é processado, e o script tenta identificar linhas completas (terminadas por `\n`).
5.  Cada linha identificada é então comparada (de forma case-insensitive) com os domínios/palavras-chave do escopo.
6.  **Se uma linha corresponde** a qualquer item do escopo:
    *   Ela é impressa no terminal.
    *   Ela é escrita em um novo arquivo com o sufixo `_scope` (ex: `documento_original_scope.txt`).
7.  Após processar todo o documento desta forma:
    *   Se pelo menos uma linha correspondente foi encontrada, o arquivo `_scope.txt` contendo apenas essas linhas é mantido. O arquivo original **não é baixado/salvo**.
    *   Se nenhuma linha correspondente foi encontrada, qualquer arquivo `_scope.txt` temporário é removido, e o arquivo original também **não é baixado**.
8.  Este comportamento se aplica apenas a `MessageMediaDocument`. `MessageMediaPhoto` (fotos) são sempre baixadas integralmente se não estiverem no histórico.

**Benefício:** Se você está procurando por informações específicas dentro de arquivos de texto de muitos Gigabytes, o modo `--onfly` permite extrair essas informações sem nunca carregar o arquivo inteiro na RAM ou ocupar espaço em disco desnecessariamente com o arquivo original.

## Segurança e Recomendações

*   **Credenciais de API:** Seus `API_ID` e `API_HASH` são sensíveis. Não os compartilhe publicamente.
*   **Arquivo de Sessão:** O Telethon criará um arquivo de sessão (ex: `my_telegram_session.session`) após o primeiro login bem-sucedido. Este arquivo contém seu token de autenticação. **NÃO COMPARTILHE ESTE ARQUIVO**.
*   **2FA (Autenticação de Dois Fatores):** Se sua conta Telegram tiver 2FA ativado, o script solicitará sua senha durante o primeiro login.
