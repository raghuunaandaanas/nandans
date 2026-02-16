# Import required libraries for broker login and symbol management
import json, os, psutil, pyotp, requests
from NorenRestApiPy.NorenApi import NorenApi
import urllib.request as u,zipfile as z,glob as g,calendar as c
from datetime import datetime,timedelta as t

# Create symbols directory if it doesn't exist
os.makedirs('symbols',exist_ok=1)

# Cleanup: Kill any existing Python processes to free up resources and ports
print("🧹 Cleaning up...")
killed = 0
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'python.exe' and proc.pid != os.getpid():
        try: proc.kill(); killed += 1
        except: pass
print(f"✓ Cleaned up {killed} processes\n")

# Download Shoonya symbol files from API for BSE, BFO, NFO, NSE, MCX exchanges
[b:='https://api.shoonya.com/',[u.urlretrieve(b+f,f'symbols/{k}_symbols.txt.zip')for k,f in[('BSE','BSE_symbols.txt.zip'),('BFO','BFO_symbols.txt.zip'),('NFO','NFO_symbols.txt.zip'),('NSE','NSE_symbols.txt.zip'),('MCX','MCX_symbols.txt.zip')]]]
# Extract all downloaded zip files and remove them after extraction
[z.ZipFile(x).extractall('symbols')for x in g.glob('symbols/*.zip')];[os.remove(x)for x in g.glob('symbols/*.zip')]

# Load broker credentials from JSON files
with open('shoonya_cred.json') as f: shoonya_cred = json.load(f)
with open('delta_cred.json') as f: delta_cred = json.load(f)

# Login to Shoonya broker using TOTP authentication
shoonya = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
totp = pyotp.TOTP(shoonya_cred['totp_secret']).now()
ret = shoonya.login(userid=shoonya_cred['userid'], password=shoonya_cred['password'], twoFA=totp, vendor_code=shoonya_cred['vendor_code'], api_secret=shoonya_cred['api_secret'], imei=shoonya_cred['imei'])
print(f"✓ Shoonya: {ret.get('uname')}")

# Login to Delta India and download all crypto symbols/products
resp = requests.get('https://api.india.delta.exchange/v2/products', headers={'api-key': delta_cred['api_key']})
products = resp.json()['result']
# Write crypto symbols to file in CSV format
with open('symbols/DELTA_symbols.txt', 'w') as f:
    for p in products: f.write(f"DELTA,{p['id']},1,{p['symbol']},{p['description']},{p['contract_type']},0,\n")
print(f"✓ Delta India: {len(products)} crypto symbols")
