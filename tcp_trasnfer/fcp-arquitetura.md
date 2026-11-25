# FCP — File Chat Protocol

## Objetivo

Protocolo de aplicação próprio, construído sobre **TCP**, para suportar:

1. Chat em tempo real;
2. Transferência de arquivos;
3. Múltiplos clientes simultaneamente.

A arquitetura está dividida em camadas:

```text
Aplicação
    ↓
FCPClient / FCPServer
    ↓
Socket / ServerSocket
    ↓
TCP
```

---

## 1. Classe `Socket`

Abstrai um socket TCP já conectado.

Sua responsabilidade principal é esconder das camadas superiores o fato de que TCP trabalha com um **fluxo de bytes**, e não com mensagens individuais.

Interface conceitual:

```python
socket.send(package)
package = socket.receive()
```

Responsabilidades:

- serialização e desserialização dos pacotes;
- framing das mensagens;
- leitura de header e payload;
- leitura exata da quantidade necessária de bytes;
- não entregar uma mensagem parcialmente recebida;
- separar mensagens que chegaram juntas no fluxo TCP;
- usar `sendall()` ou comportamento equivalente para o envio completo.

Modelo mental:

```text
TCP:
recv() → pedaços arbitrários de bytes

Socket:
receive() → exatamente um pacote completo
```

A classe `Socket` não precisa conhecer operações específicas como chat ou solicitação de arquivo. Ela conhece apenas os frames/pacotes transportados.

---

## 2. Classe `ServerSocket`

Abstrai o lado passivo do TCP.

Responsabilidades:

- executar `bind`;
- executar `listen`;
- aceitar conexões com `accept`;
- encapsular cada conexão aceita em uma instância de `Socket`.

Interface conceitual:

```python
for client_socket in server_socket.listen():
    ...
```

Cada `client_socket` representa uma conexão TCP individual já abstraída pela classe `Socket`.

O `ServerSocket` não conhece o protocolo FCP.

---

## 3. Classe `FCPClient`

Representa uma conexão FCP do lado cliente.

O cliente possui **uma thread própria de recebimento**, que permanece em loop lendo mensagens enviadas pelo servidor.

```text
                      ┌→ CHAT_MESSAGE → callback
                      │
Socket → receive loop ├→ FILE_CHUNK → transferência correspondente
                      │
                      └→ ERROR / mensagem de controle
```

### Mensagens de chat

A aplicação que instancia o cliente fornece uma callback:

```python
def on_message(message):
    ...
```

Quando uma mensagem de chat chega:

```text
Servidor
   ↓
Thread de recepção do FCPClient
   ↓
on_message(...)
```

A thread de recepção é a única responsável por receber dados do socket. Métodos como `get_file()` não devem chamar `recv()` diretamente.

---

## 4. Transferência de arquivos no cliente

A API de alto nível será semelhante a:

```python
for chunk in client.get_file("teste.txt"):
    process_chunk(chunk)
```

Fluxo esperado:

```text
get_file("teste.txt")
        ↓
envia FILE_REQUEST
        ↓
servidor envia FILE_CHUNK
        ↓
thread receptora recebe os chunks
        ↓
encaminha cada chunk para a transferência correspondente
        ↓
get_file() entrega os chunks usando yield
```

A intenção é permitir **streaming**, em vez de obrigatoriamente esperar pelo arquivo completo antes de entregá-lo à aplicação.

A comunicação entre a thread receptora e o iterador de `get_file()` pode ser implementada com uma estrutura thread-safe, como uma fila.

Exemplo conceitual:

```python
from queue import Queue

transfer_queue = Queue()
```

Ainda pode ser decidido posteriormente se os chunks serão:

- mantidos temporariamente em memória;
- colocados em uma fila limitada;
- escritos diretamente em um arquivo temporário no disco.

---

## 5. `CHUNK_SIZE`

Os arquivos serão transferidos em chunks.

```text
Arquivo completo

████████████████████████████

        ↓

[chunk 0]
[chunk 1]
[chunk 2]
[chunk 3]
...
```

O tamanho poderá ser configurado por meio de um parâmetro como:

```python
CHUNK_SIZE = 64 * 1024
```

Um **chunk FCP não corresponde necessariamente a um pacote TCP nem a uma chamada de `recv()`**.

A classe `Socket` continua responsável por reconstruir o frame completo, independentemente de como seus bytes chegaram pelo TCP.

---

## 6. Classe `FCPServer`

O `FCPServer` possui internamente um `ServerSocket` e aceita múltiplas conexões.

O próprio `FCPServer` será responsável por criar e gerenciar as threads associadas aos clientes.

```text
                    ┌→ thread do cliente A
                    │
ServerSocket ───────┼→ thread do cliente B
                    │
                    └→ thread do cliente C
```

Cada thread mantém o loop de recepção e processamento da conexão de um cliente.

A aplicação que instancia o servidor não precisa criar nem gerenciar essas threads diretamente.

---

## 7. Handlers do servidor

A aplicação que instancia o `FCPServer` fornecerá dois handlers:

```python
server = FCPServer(
    host="0.0.0.0",
    port=5000,
    on_message=handle_message,
    on_file_request=handle_file_request,
)
```

Esses handlers são callbacks locais da aplicação. Eles não são enviados pelo cliente remoto pela rede.

### `on_message`

Executado quando um cliente envia uma mensagem válida de chat.

```python
def on_message(client, message):
    ...
```

A aplicação decide o destino e o tratamento da mensagem.

### `on_file_request`

Executado quando um cliente solicita um arquivo.

```python
def on_file_request(client, filename):
    ...
```

A aplicação decide:

- se o arquivo existe;
- se o arquivo pode ser acessado;
- se o caminho está dentro do diretório permitido;
- onde o arquivo está armazenado;
- se a solicitação deve ser recusada.

Exemplo:

```python
def on_file_request(client, filename):
    if not is_allowed(filename):
        client.send_error("ACCESS_DENIED")
        return

    client.send_file(filename)
```

Por enquanto, o servidor terá somente esses dois handlers. Novos handlers somente serão adicionados caso uma nova operação real seja incorporada ao protocolo.

---

## 8. Divisão de responsabilidades

### Responsabilidades do FCP

O FCP responde à pergunta:

> Como a comunicação deve acontecer?

Ele cuida de:

- framing;
- tipos de mensagens;
- serialização e desserialização;
- transferência em chunks;
- gerenciamento das threads de conexão;
- recepção contínua de mensagens;
- identificação do tipo da mensagem;
- encaminhamento ao handler adequado;
- erros estruturais do protocolo;
- desconexões e falhas de comunicação.

Exemplos de validações do protocolo:

- o tipo da mensagem é conhecido;
- os campos obrigatórios estão presentes;
- o tamanho declarado do payload é válido;
- o frame foi recebido completamente;
- o chunk pertence a uma transferência existente.

### Responsabilidades da aplicação

A aplicação responde à pergunta:

> A operação solicitada deve ser executada?

Ela cuida de:

- verificar se um arquivo existe;
- impedir acesso a arquivos fora do diretório permitido;
- controlar autorização de acesso;
- decidir para quem uma mensagem será enviada;
- definir quais arquivos estão disponíveis;
- aplicar regras específicas do sistema.

Exemplos:

- “Este usuário pode acessar este arquivo?”
- “O caminho solicitado está dentro do diretório compartilhado?”
- “Para qual usuário ou sala esta mensagem deve ser encaminhada?”

Regra mental:

> **O FCP verifica se a mensagem é válida segundo o protocolo. A aplicação verifica se a operação solicitada faz sentido e deve ser realizada.**

---

## 9. Fluxo resumido do servidor

```text
FCPServer
   │
   ├── ServerSocket aceita uma conexão
   │
   └── FCPServer cria uma thread para o cliente
          │
          └── loop de recepção
                 │
                 ├── CHAT_MESSAGE
                 │      └── on_message(client, message)
                 │
                 ├── FILE_REQUEST
                 │      └── on_file_request(client, filename)
                 │
                 └── mensagem inválida
                        └── FCP trata como erro de protocolo
```

---

## 10. Arquitetura consolidada

```text
                         APLICAÇÃO
                             │
             ┌───────────────┴────────────────┐
             │                                │
         FCPClient                        FCPServer
             │                                │
     thread de recepção                  ServerSocket
             │                                │
      ┌──────┴──────┐                  aceita conexões
      │             │                        │
     chat         arquivos             thread por cliente
      │             │                        │
 on_message()    get_file()              receive loop
                                              │
                                     ┌────────┴────────┐
                                     │                 │
                               CHAT_MESSAGE       FILE_REQUEST
                                     │                 │
                              on_message()     on_file_request()
```

---

## 11. Decisões tomadas

- O protocolo será construído sobre TCP.
- Haverá uma classe `Socket` responsável pelo framing.
- Haverá uma classe `ServerSocket` responsável por aceitar conexões.
- O `FCPClient` terá uma thread própria de recepção.
- Apenas a thread de recepção lerá o socket do cliente.
- O chat será entregue à aplicação por uma callback `on_message`.
- `get_file()` enviará uma solicitação e entregará os chunks por iteração.
- Arquivos serão transferidos em chunks configuráveis.
- O `FCPServer` gerenciará uma thread por conexão.
- A aplicação fornecerá `on_message` e `on_file_request` ao servidor.
- O FCP validará a estrutura e o fluxo do protocolo.
- A aplicação implementará as regras de negócio.
- Mais abstrações e handlers somente serão adicionados quando houver uma necessidade concreta.

---

## 12. Pontos ainda em aberto

As seguintes decisões podem ser tomadas durante a implementação:

- formato binário exato do header;
- campos presentes em cada tipo de mensagem;
- armazenamento temporário dos chunks em memória, fila ou disco;
- uso de identificadores para correlacionar solicitações e respostas;
- tamanho padrão e tamanho máximo dos chunks;
- estratégia de encerramento das threads;
- comportamento após desconexões durante uma transferência;
- verificação final de tamanho ou hash do arquivo.
