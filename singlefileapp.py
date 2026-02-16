# Import required libraries for broker operations and status tracking
import json, os, psutil, pyotp, requests
from NorenRestApiPy.NorenApi import NorenApi
import urllib.request as u,zipfile as z,glob as g,calendar as c
from datetime import datetime,timedelta as t

# Create symbols directory if it doesn't exist
os.makedirs('symbols',exist_ok=1)

# Initialize status tracking dictionary with timestamp
status = {'timestamp': datetime.now().isoformat(), 'brokers': {}}

# Cleanup: Kill any existing Python processes to free up resources
print("🧹 Cleaning up...")
killed = 0
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] == 'python.exe' and proc.pid != os.getpid():
        try: proc.kill(); killed += 1
        except: pass
print(f"✓ Cleaned up {killed} processes\n")

# Download Shoonya symbol files from API for all exchanges
print("📥 Downloading Shoonya symbols...")
exchanges = ['BSE', 'BFO', 'NFO', 'NSE', 'MCX']
[b:='https://api.shoonya.com/',[u.urlretrieve(b+f,f'symbols/{k}_symbols.txt.zip')for k,f in[('BSE','BSE_symbols.txt.zip'),('BFO','BFO_symbols.txt.zip'),('NFO','NFO_symbols.txt.zip'),('NSE','NSE_symbols.txt.zip'),('MCX','MCX_symbols.txt.zip')]]]

# Extract all downloaded zip files and remove zip files after extraction
[z.ZipFile(x).extractall('symbols')for x in g.glob('symbols/*.zip')];[os.remove(x)for x in g.glob('symbols/*.zip')]

# Count total symbols downloaded for each Shoonya exchange
shoonya_symbols = {}
for ex in exchanges:
    with open(f'symbols/{ex}_symbols.txt') as f:
        shoonya_symbols[ex] = len(f.readlines())

# Load broker credentials from JSON configuration files
with open('shoonya_cred.json') as f: shoonya_cred = json.load(f)
with open('delta_cred.json') as f: delta_cred = json.load(f)

# Shoonya broker login with error handling and status tracking
try:
    # Initialize Shoonya API connection
    shoonya = NorenApi(host='https://api.shoonya.com/NorenWClientTP/', websocket='wss://api.shoonya.com/NorenWSTP/')
    # Generate TOTP for two-factor authentication
    totp = pyotp.TOTP(shoonya_cred['totp_secret']).now()
    # Login to Shoonya with all required credentials
    ret = shoonya.login(userid=shoonya_cred['userid'], password=shoonya_cred['password'], twoFA=totp, vendor_code=shoonya_cred['vendor_code'], api_secret=shoonya_cred['api_secret'], imei=shoonya_cred['imei'])
    # Update status with successful login and symbol counts
    status['brokers']['shoonya'] = {'login': 'success', 'user': ret.get('uname'), 'symbols': shoonya_symbols, 'total_symbols': sum(shoonya_symbols.values())}
    print(f"✓ Shoonya: {ret.get('uname')} - {sum(shoonya_symbols.values())} symbols")
except Exception as e:
    # Update status with failed login and error details
    status['brokers']['shoonya'] = {'login': 'failed', 'error': str(e), 'symbols': shoonya_symbols, 'total_symbols': sum(shoonya_symbols.values())}
    print(f"✗ Shoonya login failed: {e}")

# Delta India broker login and crypto symbols download with error handling
try:
    # Fetch all crypto products from Delta India API
    resp = requests.get('https://api.india.delta.exchange/v2/products', headers={'api-key': delta_cred['api_key']})
    products = resp.json()['result']
    # Write all crypto symbols to file in CSV format
    with open('symbols/DELTA_symbols.txt', 'w') as f:
        for p in products: f.write(f"DELTA,{p['id']},1,{p['symbol']},{p['description']},{p['contract_type']},0,\n")
    # Update status with successful login and symbol count
    status['brokers']['delta_india'] = {'login': 'success', 'symbols': {'DELTA': len(products)}, 'total_symbols': len(products)}
    print(f"✓ Delta India: {len(products)} crypto symbols")
except Exception as e:
    # Update status with failed login and error details
    status['brokers']['delta_india'] = {'login': 'failed', 'error': str(e), 'symbols': {}, 'total_symbols': 0}
    print(f"✗ Delta India failed: {e}")

# Write complete status to JSON file for monitoring
with open('status.json', 'w') as f:
    json.dump(status, f, indent=2)
print(f"\n📊 Status saved to status.json")
