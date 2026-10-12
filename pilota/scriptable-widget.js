// Widget Pilota per Scriptable (gratis). Legge Calendario e Promemoria NATIVI dell'iPhone.
// Le email sono opzionali: servono BASE e K (vedi README). Senza, il widget mostra solo agenda e promemoria.
const BASE = "";   // es. "https://tuo-progetto.vercel.app"
const K = "";      // il tuo APP_SECRET
const t0 = new Date(), t1 = new Date(Date.now() + 24 * 3600e3);
const events = (await CalendarEvent.between(t0, t1)).sort((a, b) => a.startDate - b.startDate);
let rems = [];
try { rems = (await Reminder.allIncomplete()).filter(r => r.dueDate && r.dueDate <= t1); } catch (e) {}
let mails = null;
if (BASE && K) { try { const q = new Request(`${BASE}/api/digest?k=${K}`); q.timeoutInterval = 8; mails = (await q.loadJSON()).mails || []; } catch (e) {} }

// Notifiche locali: 10 minuti prima di ogni appuntamento (si aggiornano a ogni esecuzione)
for (const e of events.filter(e => !e.isAllDay)) {
  const when = new Date(e.startDate.getTime() - 10 * 60e3);
  if (when > new Date()) { const n = new Notification(); n.identifier = "ev-" + e.identifier; n.title = e.title; n.body = "Tra 10 minuti" + (e.location ? " · " + e.location : ""); n.scheduledDate = when; await n.schedule(); }
}

const w = new ListWidget();
w.backgroundColor = new Color("#14213D"); w.url = BASE || "calshow://";
w.refreshAfterDate = new Date(Date.now() + 15 * 60e3);
const small = config.widgetFamily === "small";
const line = (s, size, color = "#E8ECF2", bold = false) => { const x = w.addText(String(s)); x.textColor = new Color(color); x.font = bold ? Font.boldSystemFont(size) : Font.systemFont(size); x.lineLimit = 1; return x; };
const hm = d => d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
const timed = events.filter(e => !e.isAllDay && e.endDate > new Date());
const next = timed[0] || events[0];
if (next) {
  const mins = Math.round((next.startDate - new Date()) / 6e4);
  line(next.isAllDay ? "Oggi" : mins <= 0 ? "In corso" : mins < 60 ? `Tra ${mins} min` : hm(next.startDate), 12, "#3FCBA5", true);
  line(next.title, small ? 15 : 17, "#FFFFFF", true);
} else line("Agenda libera", 16, "#FFFFFF", true);
w.addSpacer(6);
if (!small) timed.slice(1, 3).forEach(e => { line(`${hm(e.startDate)}  ${e.title}`, 13); w.addSpacer(2); });
if (rems.length) line(`☑︎ ${rems.length} promemoria: ${rems[0].title}`, 12, "#E0A83A");
if (mails) { const c = { alta: "#EE7A72", media: "#E0A83A", bassa: "#93A0B5" }; w.addSpacer(4);
  if (small) line(`✉︎ ${mails.length} da leggere`, 12, "#93A0B5");
  else mails.slice(0, 2).forEach(m => line(`● ${m.from}: ${m.subject}`, 12, c[m.priority] || "#E8ECF2")); }
if (config.runsInWidget) Script.setWidget(w); else await w.presentMedium();
Script.complete();
