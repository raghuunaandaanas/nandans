import json, os, psutil, pyotp, requests
from NorenRestApiPy.NorenApi import NorenApi
import urllib.request as u,zipfile as z,glob as g,calendar as c
from datetime import datetime,timedelta as t
os.makedirs('symbols',exist_ok=1)

# Cleanup
print("🧹 Cleaning up...")
killed = 0
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'python.exe' and proc.pid != os.getpid():
        try: proc.kill(); killed += 1
        except: pass
print(f"✓ Cleaned up {killed} processes\n")

# Download Shoonya symbols
[b:='https://api.shoonya.com/',[u.urlretrieve(b+f,f'symbols/{k}_symbols.txt.zip')for k,f in[('BSE','BSE_symbols.txt.zip'),('BFO','BFO_symbols.txt.zip'),('NFO','NFO_symbols.txt.zip'),('NSE','NSE_symbols.txt.zip'),('MCX','MCX_symbols.txt.zip')]]]
[z.ZipFile(x).extractall('symbols')for x in g.glob('symbols/*.zip')];[os.remove(x)for x in g.glob('symbols/*.zip')]

# Load credentials
with open('shoonya_cred.json') as f: shoonya_cred = json.load(f)
with open('delta_cred.json') as f: delta_cred = json.load(f)

# Shoonya login
shoonya = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
totp = pyotp.TOTP(shoonya_cred['totp_secret']).now()
ret = shoonya.login(userid=shoonya_cred['userid'], password=shoonya_cred['password'], twoFA=totp, vendor_code=shoonya_cred['vendor_code'], api_secret=shoonya_cred['api_secret'], imei=shoonya_cred['imei'])
print(f"✓ Shoonya: {ret.get('uname')}")

# Delta India - download crypto symbols
resp = requests.get('https://api.india.delta.exchange/v2/products', headers={'api-key': delta_cred['api_key']})
products = resp.json()['result']
with open('symbols/DELTA_symbols.txt', 'w') as f:
    for p in products: f.write(f"DELTA,{p['id']},1,{p['symbol']},{p['description']},{p['contract_type']},0,\n")
print(f"✓ Delta India: {len(products)} crypto symbols")
