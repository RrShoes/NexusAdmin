import socketio
import time
import socket
import os
import subprocess
import re
import threading
import urllib.request
import urllib.parse

sio = socketio.Client()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_wmic_query(query):
    # CREATE_NO_WINDOW = 0x08000000 para não piscar tela do CMD
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    try:
        output = subprocess.check_output(
            query, 
            stderr=subprocess.STDOUT, 
            startupinfo=startupinfo,
            creationflags=0x08000000,
            encoding='oem', errors='replace'
        )
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        if len(lines) > 1:
            # Pula o header (índice 0) e retorna os dados unidos (pode ser mais de 1 linha dependendo do disco)
            return " | ".join(lines[1:])
        return "N/A"
    except Exception as e:
        return f"Erro"

def get_hostname():
    return socket.gethostname()

def get_disk_info():
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        output = subprocess.check_output(
            ["wmic", "diskdrive", "get", "model,size"], 
            stderr=subprocess.STDOUT, 
            startupinfo=startupinfo,
            creationflags=0x08000000,
            encoding='oem', errors='replace'
        )
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        if len(lines) > 1:
            disks = []
            for line in lines[1:]:
                parts = line.split()
                if not parts:
                    continue
                # O último elemento costuma ser o tamanho em bytes
                if parts[-1].isdigit():
                    size_bytes = int(parts[-1])
                    size_gb = round(size_bytes / (1024**3))
                    model = " ".join(parts[:-1])
                    disks.append(f"{model} ({size_gb} GB)")
                else:
                    disks.append(line)
            return " | ".join(disks)
        return "N/A"
    except Exception:
        return "Erro"

def get_ram_type():
    mapping = {
        "20": "DDR", "21": "DDR2", "22": "DDR2 FB-DIMM",
        "24": "DDR3", "26": "DDR4", "34": "DDR5"
    }
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Tenta pegar pelo SMBIOS (funciona melhor para DDR4 e DDR5)
        out_smbios = subprocess.check_output(
            ["wmic", "memorychip", "get", "smbiosmemorytype"], 
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, encoding='oem', errors='replace'
        )
        lines = [l.strip() for l in out_smbios.split('\n') if l.strip()]
        if len(lines) > 1 and lines[1] in mapping:
            return mapping[lines[1]]
            
        # Fallback para MemoryType clássico
        out_mem = subprocess.check_output(
            ["wmic", "memorychip", "get", "memorytype"], 
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, encoding='oem', errors='replace'
        )
        lines_mem = [l.strip() for l in out_mem.split('\n') if l.strip()]
        if len(lines_mem) > 1 and lines_mem[1] in mapping:
            return mapping[lines_mem[1]]
            
        return ""
    except Exception:
        return ""

def get_os_info():
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        out_os = subprocess.check_output(
            ["wmic", "os", "get", "caption,version"], 
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, encoding='oem', errors='replace'
        )
        lines = [l.strip() for l in out_os.split('\n') if l.strip()]
        os_str = "Windows"
        if len(lines) > 1:
            os_str = re.sub(r'\s+', ' ', lines[1]).replace("Microsoft ", "")
            
        out_arch = subprocess.check_output(
            ["wmic", "os", "get", "osarchitecture"], 
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, encoding='oem', errors='replace'
        )
        lines_arch = [l.strip() for l in out_arch.split('\n') if l.strip()]
        arch_str = ""
        if len(lines_arch) > 1:
            arch_str = lines_arch[1]
            
        if arch_str:
            return f"{os_str} ({arch_str})"
        return os_str
    except Exception:
        return "N/A"

def get_logged_in_user():
    import csv
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        output = subprocess.check_output(
            ["tasklist", "/V", "/FI", "IMAGENAME eq explorer.exe", "/FO", "CSV"],
            stderr=subprocess.STDOUT, 
            startupinfo=startupinfo,
            creationflags=0x08000000,
            encoding='oem', errors='replace'
        )
        lines = [line.strip() for line in output.split('\n') if line.strip()]
        if len(lines) > 1:
            reader = csv.reader(lines)
            next(reader)
            for row in reader:
                if len(row) > 6:
                    user = row[6]
                    if user and user.upper() not in ["N/A", "SYSTEM", ""]:
                        return user
        return "N/A"
    except Exception:
        return "N/A"

def collect_data():
    hostname = get_hostname()
    user = get_logged_in_user()
    if user == "N/A":
        user = run_wmic_query(["wmic", "computersystem", "get", "username"])
    ip = get_local_ip()
    cpu = run_wmic_query(["wmic", "cpu", "get", "name"])
    gpu = run_wmic_query(["wmic", "path", "win32_VideoController", "get", "name"])
    monitor = run_wmic_query(["wmic", "desktopmonitor", "get", "description"])
    motherboard = run_wmic_query(["wmic", "baseboard", "get", "product"])
    disk = get_disk_info()
    
    ram_type = get_ram_type()
    ram_bytes_str = run_wmic_query(["wmic", "computersystem", "get", "totalphysicalmemory"])
    try:
        ram_gb = round(int(ram_bytes_str.replace(" | ", "")) / (1024**3))
        ram = f"{ram_gb} GB"
        if ram_type:
            ram += f" ({ram_type})"
    except Exception:
        ram = "N/A"
        
    chassis_raw = run_wmic_query(["wmic", "systemenclosure", "get", "chassistypes"])
    chassis_clean = chassis_raw.replace("{", "").replace("}", "").replace(" | ", "").strip()
    chassis_mapping = {
        "3": "Desktop", "4": "Desktop", "6": "Mini Tower", "7": "Tower",
        "8": "Portable", "9": "Laptop", "10": "Notebook", "11": "Hand Held",
        "13": "All in One", "14": "Sub Notebook", "30": "Tablet", "31": "Convertible", "32": "Detachable"
    }
    chassis_name = chassis_mapping.get(chassis_clean, f"Outro ({chassis_raw})") if chassis_clean and chassis_clean != "N/A" else "N/A"
    
    return {
        "user": user,
        "hostname": hostname,
        "chassis": chassis_name,
        "os": get_os_info(),
        "ip": ip,
        "cpu": cpu,
        "gpu": gpu,
        "monitor": monitor,
        "motherboard": motherboard,
        "disk": disk,
        "ram": ram
    }

def registrar_async():
    try:
        dados = collect_data()
        sio.emit('registrar_hardware', dados)
        print("[+] Dados completos enviados!")
    except Exception as e:
        print("Erro ao coletar dados completos:", e)

def atualizar_dinamico_loop():
    # Loop que roda a cada 60 segundos para atualizar apenas Usuário e IP
    # Evita rodar os comandos pesados de hardware (wmic cpu, placa mãe, etc)
    while True:
        time.sleep(60)
        if sio.connected:
            try:
                user = get_logged_in_user()
                if user == "N/A":
                    user = run_wmic_query(["wmic", "computersystem", "get", "username"])
                
                dados_leves = {
                    "hostname": get_hostname(),
                    "user": user,
                    "ip": get_local_ip()
                }
                sio.emit('registrar_hardware', dados_leves)
                print("[+] Dados de Usuário/IP atualizados!")
            except Exception as e:
                pass

@sio.event
def connect():
    print("[+] Conectado ao servidor!")
    threading.Thread(target=registrar_async).start()

@sio.event
def disconnect():
    print("[-] Desconectado do servidor.")

@sio.on('executar_acao')
def on_executar_acao(data):
    acao = data.get('acao')
    print(f"[!] Comando recebido: {acao}")
    
    if acao == 'desligar':
        os.system("shutdown /s /f /t 0")
    elif acao == 'reiniciar':
        os.system("shutdown /r /f /t 0")

def verificar_instalar_meshagent(server_url):
    hostname = get_hostname()
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # 1. Verificação do Serviço
        try:
            subprocess.check_output(
                ["sc", "query", "MeshAgent"],
                stderr=subprocess.STDOUT,
                startupinfo=startupinfo,
                creationflags=0x08000000,
                encoding='oem', errors='replace'
            )
            # Se o comando não falhar, o serviço existe e possivelmente está rodando
            return
        except subprocess.CalledProcessError:
            # Serviço não existe, o comando 'sc query' retornou erro. Segue o fluxo.
            pass
            
        # 2. Condicional de Ação: Instalação silenciosa
        try:
            # Verifica se estamos em ambiente de testes no desktop (desenvolvimento) ou em produção
            import getpass
            current_user = getpass.getuser()
            
            # Caminho da rede onde está o instalador do MeshAgent
            mesh_installer_path = r"\\srv-fs1\NFe\TI\NexusAdminRemoto\NexusAdmin\meshagent64.exe"
            
            # Se não achar na rede, tenta achar no diretório atual
            if not os.path.exists(mesh_installer_path):
                print(f"[MeshCentral] Instalador {mesh_installer_path} não encontrado na rede.")
                
                import sys
                if getattr(sys, 'frozen', False):
                    # Se for um executável compilado (.exe)
                    base_dir = os.path.dirname(sys.executable)
                else:
                    # Se for rodado como script .py
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    
                mesh_installer_path = os.path.join(base_dir, "meshagent64.exe")
                
                if not os.path.exists(mesh_installer_path):
                    print(f"[MeshCentral] Instalador local {mesh_installer_path} também não encontrado.")
                    return
                print(f"[MeshCentral] Usando instalador local: {mesh_installer_path}")

            print("[MeshCentral] Instalando MeshAgent silenciosamente...")
            
            import shutil
            # Copiar para um local temporário para evitar problemas de permissão em rede elevada
            temp_installer = os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), "meshagent64.exe")
            try:
                shutil.copy2(mesh_installer_path, temp_installer)
                print(f"[MeshCentral] Copiado para {temp_installer}")
                exec_path = temp_installer
            except Exception as e:
                print(f"[MeshCentral] Erro ao copiar, tentando executar direto. Erro: {e}")
                exec_path = mesh_installer_path

            # Executa o instalador do MeshAgent de forma silenciosa
            subprocess.check_call(
                [exec_path, "-fullinstall"],
                startupinfo=startupinfo,
                creationflags=0x08000000
            )
            print("[MeshCentral] MeshAgent instalado com sucesso!")
            
            try:
                print("[MeshCentral] Blindando serviço: Removendo flag interativa (Erro 7030)...")
                subprocess.check_call(
                    ["sc", "config", "Mesh Agent", "type=", "own"],
                    startupinfo=startupinfo,
                    creationflags=0x08000000
                )
                
                print("[MeshCentral] Blindando serviço: Garantindo inicialização automática...")
                subprocess.check_call(
                    ["sc", "config", "Mesh Agent", "start=", "auto"],
                    startupinfo=startupinfo,
                    creationflags=0x08000000
                )
                
                print("[MeshCentral] Blindando serviço: Forçando a iniciação do serviço...")
                subprocess.check_call(
                    ["sc", "start", "Mesh Agent"],
                    startupinfo=startupinfo,
                    creationflags=0x08000000
                )
                
                print("[MeshCentral] Serviço blindado e iniciado com sucesso!")
            except Exception as e:
                print(f"[MeshCentral] Erro durante a blindagem do serviço: {e}")
                
            status = "sucesso"
        except Exception as e:
            print(f"[MeshCentral] Falha na instalação: {e}")
            status = f"falha - {str(e)}"
            
        # 3. Notificação ao Servidor (usando biblioteca nativa urllib)
        notificar_url = f"{server_url}/api/notificar_instalacao"
        data = urllib.parse.urlencode({'hostname': hostname, 'status': status}).encode('utf-8')
        req = urllib.request.Request(notificar_url, data=data)
        urllib.request.urlopen(req, timeout=10)
        
    except Exception as e:
        print(f"Erro na rotina do MeshCentral: {e}")

def main():
    # ATENÇÃO: Substitua 10.0.2.204 pelo IP real do seu servidor se ele for diferente!
    server_url = "http://10.0.1.116:5018"
    
    # Executa a rotina do MeshCentral assim que o agente iniciar
    verificar_instalar_meshagent(server_url)
    
    # Inicia a thread que vai ficar checando o usuário a cada 1 minuto
    threading.Thread(target=atualizar_dinamico_loop, daemon=True).start()

    print(f"Tentando conectar ao servidor em {server_url}...")
    
    while True:
        try:
            sio.connect(server_url)
            sio.wait()
        except Exception:
            pass # Falha na conexão, aguarda e tenta novamente
            
        time.sleep(5)

if __name__ == '__main__':
    main()
