import urllib.request as u,zipfile as z,os,glob as g,calendar as c
from datetime import datetime,timedelta as t
os.makedirs('symbols',exist_ok=1)
[b:='https://api.shoonya.com/',[u.urlretrieve(b+f,f'symbols/{k}_symbols.txt.zip')for k,f in[('BSE','BSE_symbols.txt.zip'),('BFO','BFO_symbols.txt.zip'),('NFO','NFO_symbols.txt.zip'),('NSE','NSE_symbols.txt.zip'),('MCX','MCX_symbols.txt.zip')]]]
[z.ZipFile(x).extractall('symbols')for x in g.glob('symbols/*.zip')]
[os.remove(x)for x in g.glob('symbols/*.zip')]
n=datetime.now();cm=n.strftime('%b').upper()+'-'+str(n.year);nm=(n+t(days=31)).strftime('%b').upper()+'-'+str((n+t(days=31)).year);ld=c.monthrange(n.year,n.month)[1];lw=n.day>ld-7
d=open('symbols/BFO_symbols.txt').readlines();open('symbols/BFO_symbols.txt','w').writelines([l for l in d if('FUTIDX'in l or'OPTIDX'in l)and(cm in l.upper()or(lw and nm in l.upper()))])
d=open('symbols/MCX_symbols.txt').readlines();open('symbols/MCX_symbols.txt','w').writelines([l for l in d if('FUTCOM'in l or'OPTFUT'in l)and(cm in l.upper()or(lw and nm in l.upper()))])
d=open('symbols/NFO_symbols.txt').readlines();open('symbols/NFO_symbols.txt','w').writelines([l for l in d if('FUTSTK'in l or'OPTSTK'in l or'FUTIDX'in l or'OPTIDX'in l)and(cm in l.upper()or(lw and nm in l.upper()))])
d=open('symbols/BSE_symbols.txt').readlines();open('symbols/BSE_symbols.txt','w').writelines([l for l in d if'INDEX'in l.upper()])
d=open('symbols/NSE_symbols.txt').readlines();open('symbols/NSE_symbols.txt','w').writelines([l for l in d if('-EQ'in l or'INDEX'in l)and'NSETEST'not in l])
c=open('symbols/custom.txt','w');c.writelines([l for l in open('symbols/BFO_symbols.txt').readlines()if'FUTIDX'in l]);c.writelines([l for l in open('symbols/MCX_symbols.txt').readlines()if'FUTCOM'in l]);c.writelines([l for l in open('symbols/NFO_symbols.txt').readlines()if'FUTSTK'in l or'FUTIDX'in l]);c.writelines([l for l in open('symbols/NSE_symbols.txt').readlines()if'INDEX'in l])
