const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();
const fs = require('fs');
const readline = require('readline');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: { origin: "*" }
});

// Serve arquivos estáticos da pasta public
app.use(express.static(path.join(__dirname, 'public')));

// Middleware para processar JSON e urlencoded
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.post('/api/notificar_instalacao', (req, res) => {
  // Pegando 'hostname' (ou 'pc' se preferir)
  const { hostname, status } = req.body;
  console.log(`[MeshCentral] Máquina ${hostname} reportou status: ${status}`);
  res.sendStatus(200);
});

// Configuração do SQLite
const db = new sqlite3.Database(path.join(__dirname, 'database.sqlite'), (err) => {
  if (err) {
    console.error('Erro ao abrir o banco de dados', err.message);
  } else {
    console.log('Conectado ao banco de dados SQLite.');
    db.run(`CREATE TABLE IF NOT EXISTS setores (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      nome TEXT NOT NULL,
      icone TEXT
    )`);
    db.run(`CREATE TABLE IF NOT EXISTS maquinas_setores (
      hostname TEXT PRIMARY KEY,
      setor_id INTEGER
    )`);
  }
});

function broadcastSetores() {
  db.all('SELECT * FROM setores', [], (err, rows_setores) => {
    if (err) return console.error(err);
    db.all('SELECT * FROM maquinas_setores', [], (err, rows_maquinas) => {
      if (err) return console.error(err);
      
      const designacoes = {};
      rows_maquinas.forEach(r => designacoes[r.hostname] = r.setor_id);
      
      io.emit('atualizar_setores', { setores: rows_setores, designacoes });
    });
  });
}

const computadores = {};
const socketToHostname = {};

async function getMeshCentralNodes() {
  const dbPath = 'C:\\Aplicacoes\\Centro_de_monitoramento_de_pc_via_uno\\MeshCentral\\meshcentral-data\\meshcentral.db';
  const nodes = {};
  if (!fs.existsSync(dbPath)) return nodes;
  
  const fileStream = fs.createReadStream(dbPath);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });

  for await (const line of rl) {
    if (line.trim()) {
      try {
        const doc = JSON.parse(line);
        if (doc.type === 'node' && doc.name && doc._id) {
          // Remove o prefixo "node//" do ID pois o MeshCentral espera apenas o hash no &gotonode=
          const cleanId = doc._id.replace(/^node\/\//, '');
          nodes[doc.name.toUpperCase()] = cleanId; 
        }
      } catch (e) {}
    }
  }
  return nodes;
}

async function enviarListaPcsAtualizada(alvo = io) {
  const meshNodes = await getMeshCentralNodes();
  console.log('[DEBUG] Nodes MeshCentral encontrados:', Object.keys(meshNodes).length, '→', JSON.stringify(Object.keys(meshNodes)));
  const lista = Object.values(computadores).map(pc => {
    const nodeId = meshNodes[pc.hostname.toUpperCase()] || null;
    console.log(`[DEBUG] ${pc.hostname.toUpperCase()} → meshNodeId: ${nodeId ? nodeId.substring(0, 20) + '...' : 'NULL'}`);
    return { ...pc, meshNodeId: nodeId };
  });
  alvo.emit('atualizar_lista_pcs', lista);
}

io.on('connection', (socket) => {
  console.log(`[+] Nova conexão: ${socket.id}`);

  // Envia a lista atual de PCs para o novo cliente (ex: quando dá F5 no navegador)
  enviarListaPcsAtualizada(socket);
  
  // Envia a lista de setores logo após conectar
  db.all('SELECT * FROM setores', [], (err, rows_setores) => {
    if (err) return console.error(err);
    db.all('SELECT * FROM maquinas_setores', [], (err, rows_maquinas) => {
      if (err) return console.error(err);
      const designacoes = {};
      rows_maquinas.forEach(r => designacoes[r.hostname] = r.setor_id);
      socket.emit('atualizar_setores', { setores: rows_setores, designacoes });
    });
  });

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
    enviarListaPcsAtualizada(io);
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
      enviarListaPcsAtualizada(io);
    }
  });

  // Evento: criar_setor
  socket.on('criar_setor', (data) => {
    db.run('INSERT INTO setores (nome, icone) VALUES (?, ?)', [data.nome, data.icone], function(err) {
      if (err) return console.error(err);
      broadcastSetores();
    });
  });

  // Evento: remover_setor
  socket.on('remover_setor', (id) => {
    db.run('DELETE FROM setores WHERE id = ?', [id], function(err) {
      if (err) return console.error(err);
      // Opcional: Remover designações que usavam esse setor
      db.run('DELETE FROM maquinas_setores WHERE setor_id = ?', [id], () => {
        broadcastSetores();
      });
    });
  });

  // Evento: designar_setor
  socket.on('designar_setor', (data) => {
    const { hostname, setor_id } = data;
    if (setor_id === null || setor_id === '') {
      db.run('DELETE FROM maquinas_setores WHERE hostname = ?', [hostname], function(err) {
        if (err) return console.error(err);
        broadcastSetores();
      });
    } else {
      db.run('INSERT INTO maquinas_setores (hostname, setor_id) VALUES (?, ?) ON CONFLICT(hostname) DO UPDATE SET setor_id = ?', 
      [hostname, setor_id, setor_id], function(err) {
        if (err) return console.error(err);
        broadcastSetores();
      });
    }
  });
});

const PORT = 5018;
server.listen(PORT, () => {
  console.log(`Servidor rodando na porta ${PORT}`);
});
