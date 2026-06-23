const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" }
});

// Serve arquivos estáticos da pasta public
app.use(express.static(path.join(__dirname, 'public')));

// Dicionário em memória: computadores[hostname] = data
const computadores = {};
const socketToHostname = {};

io.on('connection', (socket) => {
  console.log(`[+] Nova conexão: ${socket.id}`);

  // Envia a lista atual de PCs para o novo cliente (ex: quando dá F5 no navegador)
  socket.emit('atualizar_lista_pcs', Object.values(computadores));

  // Evento: registrar_hardware
  socket.on('registrar_hardware', (data) => {
    const hostname = data.hostname;
    computadores[hostname] = {
      ...computadores[hostname],
      id: socket.id,
      ...data,
      status: 'online',
      ultimaVez: new Date().toLocaleString()
    };
    socketToHostname[socket.id] = hostname;
    
    console.log(`[+] Máquina registrada/online: ${hostname} (${data.ip})`);
    
    // Emite para o frontend a lista atualizada
    io.emit('atualizar_lista_pcs', Object.values(computadores));
  });

  // Evento: solicitar_comando (vindo do Frontend)
  socket.on('solicitar_comando', (dados_comando) => {
    const { socket_id_alvo, acao } = dados_comando;
    console.log(`[>] Comando '${acao}' solicitado para socket ${socket_id_alvo}`);
    
    // Repassa comando
    io.to(socket_id_alvo).emit('executar_acao', { acao });
  });

  // Evento: desconexão
  socket.on('disconnect', () => {
    console.log(`[-] Conexão encerrada: ${socket.id}`);
    const hostname = socketToHostname[socket.id];
    if (hostname && computadores[hostname]) {
      computadores[hostname].status = 'offline';
      delete socketToHostname[socket.id];
      // Atualiza o frontend para mostrar que a máquina ficou offline
      io.emit('atualizar_lista_pcs', Object.values(computadores));
    }
  });
});

const PORT = 5018;
server.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
});
