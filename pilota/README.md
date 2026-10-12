# Pilota: widget iPhone con Calendario nativo, Promemoria e email

## Cosa usa
- **Calendario e Promemoria nativi iOS**: li legge il widget Scriptable direttamente dal telefono. Nessun account, nessun server. In più programma notifiche 10 minuti prima di ogni evento.
- **Mail**: iOS non permette a nessuna app di leggere Mail. Per riassunto e bozze si usa l'API di Gmail (facoltativo). "Rispondi" e il pulsante Mail aprono l'app Mail nativa.

## 1. Widget (5 minuti, solo iPhone)
1. Installa **Scriptable** (gratis).
2. Nuovo script → incolla `scriptable-widget.js` → consenti l'accesso a Calendario e Promemoria quando richiesto.
3. Home → aggiungi widget Scriptable (piccolo o medio) → Modifica widget → scegli lo script.

## 2. Email (facoltativo)
1. Google Cloud → nuovo progetto → abilita **Gmail API** → credenziali OAuth "Web" con redirect `https://developers.google.com/oauthplayground`.
2. OAuth Playground → usa le tue credenziali → scope `gmail.readonly` (e `calendar.readonly` se vuoi anche Google Calendar nella PWA) → copia il **refresh token**.
3. Vercel (free): importa la cartella e imposta `G_CLIENT_ID`, `G_CLIENT_SECRET`, `G_REFRESH_TOKEN`, `GEMINI_API_KEY`, `APP_SECRET`.
4. Apri `https://TUO-PROGETTO.vercel.app/?k=APP_SECRET` in Safari → Aggiungi alla Home.
5. Compila `BASE` e `K` in cima a `scriptable-widget.js`.

## Push sulla repo
`./push.sh https://github.com/TUO-UTENTE/research-agent.git` (copia tutto nella cartella `pilota/` e fa commit + push).
