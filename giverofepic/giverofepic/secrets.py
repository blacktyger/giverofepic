import platform

WALLET_PASSWORD = 'majkut11'

if 'windows' in platform.system().lower():
    WALLET_DIR = r"C:\Users\blacktyger\.epic\main"
else:
    WALLET_DIR = "/home/blacktyger/.epic/main"