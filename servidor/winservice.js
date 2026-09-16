const Service = require('node-windows').Service;
const path = require('path');

// Configuração do serviço do Windows
const svc = new Service({
  name: 'NexusAdminServer',
  displayName: 'Servidor NexusAdmin',
  description: 'Servidor do Centro de Monitoramento de PC via Uno (NexusAdmin)',
  script: path.join(__dirname, 'server.js'),
  wait: 2,
  grow: 0.5
});

// Evento disparado quando o serviço é instalado
svc.on('install', function() {
  console.log('Serviço Servidor NexusAdmin instalado com sucesso!');
  svc.start();
});

// Evento quando já está instalado
svc.on('alreadyinstalled', function() {
  console.log('Serviço Servidor NexusAdmin já está instalado.');
});

// Evento disparado quando o serviço é desinstalado
svc.on('uninstall', function() {
  console.log('Serviço Servidor NexusAdmin desinstalado.');
});

// Processamento dos argumentos passados por linha de comando
const action = process.argv[2];
if (action === '--install') {
  svc.install();
} else if (action === '--uninstall') {
  svc.uninstall();
} else if (action === '--start') {
  svc.start();
} else if (action === '--stop') {
  svc.stop();
} else {
  console.log('Uso: node winservice.js [--install | --uninstall | --start | --stop]');
}
