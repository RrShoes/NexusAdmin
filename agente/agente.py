import socketio
import time
import socket
import os
import subprocess
import re
import threading

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
            text=True
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
            text=True
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
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, text=True
        )
        lines = [l.strip() for l in out_smbios.split('\n') if l.strip()]
        if len(lines) > 1 and lines[1] in mapping:
            return mapping[lines[1]]
            
        # Fallback para MemoryType clássico
        out_mem = subprocess.check_output(
            ["wmic", "memorychip", "get", "memorytype"], 
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, text=True
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
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, text=True
        )
        lines = [l.strip() for l in out_os.split('\n') if l.strip()]
        os_str = "Windows"
        if len(lines) > 1:
            os_str = re.sub(r'\s+', ' ', lines[1]).replace("Microsoft ", "")
            
        out_arch = subprocess.check_output(
            ["wmic", "os", "get", "osarchitecture"], 
            stderr=subprocess.STDOUT, startupinfo=startupinfo, creationflags=0x08000000, text=True
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

def collect_data():
    hostname = get_hostname()
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
        print("[+] Dados atualizados enviados!")
    except Exception as e:
        print("Erro ao coletar dados:", e)

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

def main():
    # ATENÇÃO: Substitua 10.0.2.204 pelo IP real do seu servidor se ele for diferente!
    server_url = "http://10.0.2.204:5018"
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
