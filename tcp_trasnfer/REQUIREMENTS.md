# Planning

- Protocolo de aplicação
cliente:
    - get_file
    - send_chat
    - payload com header type + size + data
servidor:
    - listen -> retorna uma connection
    - update_clients_chat -> envia 

connection:
    - possui metodos para enviar dados de volta para o cliente
