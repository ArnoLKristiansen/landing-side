from getpass import getpass
from storage import DATA, connect
connect().close()
key=getpass('Indsæt OpenAI Admin API-nøgle (skjult): ').strip()
if not key.startswith('sk-'): raise SystemExit('Ingen gyldig nøgle gemt.')
p=DATA/'openai-admin-key'
import os
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:f.write(key)
p.chmod(0o600)
print('Nøglen er gemt privat på serveren. Henter statistik…')
try:
    from api_sync import sync
    sync(); print('API-statistik opdateret.')
except Exception:
    print('Kunne ikke hente statistik. Kontrollér Admin-nøglens rettigheder og netværket.')
