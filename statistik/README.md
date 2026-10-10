# ALKData · OpenAI Forbrug

Lokal webapp på http://192.168.1.59:8086. Python 3.9+ uden eksterne biblioteker.

## Data

- Codex: lokalt gemte tokenmålinger fra Mac, inklusive arkiverede sessioner. Kun tal, model og opgave-id sendes via SSH. Samtaletekster, kode, kontotokens og API-nøgler sendes aldrig.
- Moderne sessioner bruger per-response `token_usage_record`, deduplikeret på response-id. Ældre sessioner bruger differencer i kumulative `token_count`. Formatet er en intern lokal log og kan ændres; sammenhold større afvigelser med OpenAI.
- Kontoens aktuelle grænser hentes læsende via Codex app-server proxy, når den er tilgængelig. Ellers bruges seneste logmåling med synlig alder. Udløbne vinduer vises som ukendte indtil ny måling, aldrig automatisk som 100 %.
- API-organisationsdata: valgfri Admin API-nøgle via `python3 configure_api.py`. Henter tekst/modelkald og embeddings for seneste 90 dage med pagination. Dage er UTC. Øvrige API-produkter og saldo er ikke med. Organisationens projekter kan navngives i dashboardet. En nøgle kræver passende læserettigheder.
- Funktionsmålinger er en separat visning og lægges aldrig oven i organisationsdata. Automatisk historisk funktionsfordeling er ikke tilgængelig.
- Input inkluderer cache; samlet = input + output. Reasoning-output er allerede inkluderet i output og lægges ikke til igen.
- Abonnementsprocenter er ikke en token- eller pengebeholdning. Fornyelsesdag, plan og månedspris angives manuelt. Næste fornyelse beregnes automatisk og er uafhængig af reset-tider. API afregnes separat.

## Installation på server

Appen kører som `arno` via en systemd-brugertjeneste `openai-forbrug.service`, bundet til 192.168.1.59:8086. Den er kun beregnet til det betroede lokalnet og har ikke brugerlogin. Der åbnes ikke routerporte eller eksternt domæne. Beskyt med login og HTTPS før eventuel offentlig adgang. Kun faste statiske filer serveres; nøgler og database ligger uden for webroden. Nøgler gemmes med filrettighed 600. Browserændringer kræver korrekt Host og samme Origin.

```
systemctl --user status openai-forbrug
systemctl --user restart openai-forbrug
journalctl --user -u openai-forbrug
```

Automatisk start uden brugerlogin kræver, at `Linger=yes` allerede er slået til. Hvis ikke: `sudo loginctl enable-linger arno`.

## API-måling i et Python-program

Tilføj `/home/arno/openai-forbrug` til programmets Python importsti, eller pak `usage_tracker.py` og `storage.py` med programmet og sæt `FORBRUG_DATA` til samme data-mappe. Programmet skal have adgang som arno. Containere kræver eksplicit deling af datamappen; dette er ikke automatisk installeret i eksisterende programmer.

```python
from usage_tracker import record_usage
# Efter dit eksisterende OpenAI-kald:
record_usage(response, program="Mit program", function="Opsummér tekst")
```

Funktionen kræver response-id og usage-tal. Understøtter Responses og Chat Completions; for streaming bruges den afsluttende usage-bærende respons. Kald det én gang pr. API-respons; genindlæsning med samme response-id tælles ikke dobbelt. Instrumenteringens timestamp er registreringstidspunktet. Undlad at lade målefejl stoppe kritiske programfunktioner: håndtér undtagelser i kaldende program.

## Mac-synkronisering

`collector.py` køres hvert 120. sekund af launchd og sender allowlistede målinger via eksisterende SSH-nøgle. Mac skal være vågen, Codex-sessioner læsbare og serveren tilgængelig på lokalnet/VPN. LaunchAgent installeres i brugerens Library/LaunchAgents, med brugerens tilladelse. Filen er installeret; aktivering med launchctl kræver brugerens Terminal, hvis Codex ikke har adgang til launchd. `collector.py --no-live` kan bruges til kun at importere lokale logs. En manglende live-kontoforbindelse påvirker ikke lokal tokenhistorik.

## Validering

`python3 -m unittest -v test_usage.py` tester deduplikering, cache, datogrænser, labels, adskillelse af API-kilder og ugyldige tokenantal.

Officielle kilder: https://learn.chatgpt.com/docs/app-server og https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/completions

## Aktivér Mac-opdatering

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dk.alkdata.openai-forbrug.plist
```

Stop: `launchctl bootout gui/$(id -u)/dk.alkdata.openai-forbrug`. Kildekoden ligger under outputs/openai-forbrug og skal blive liggende, mens opgaven er installeret.
