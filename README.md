# Alkdata landing page og statistik

Dette repository indeholder ALKDatas landing page med brandlogo og links til de lokale tjenester. Statistikprogrammet for OpenAI-forbrug ligger i mappen `statistik/`.

## Landing page

Nginx-containeren konfigureres med `docker-compose.yml` og serveres på port 8081. `Dockerfile` kopierer sidens HTML, CSS, profilbillede og logo ind i webroden.

## Statistik

Se `statistik/README.md` for lokal opstart og krav. Statistikprogrammets runtime-data, database, sikkerhedskopier og API-nøgle skal konfigureres separat på serveren og er udeladt fra Git.
