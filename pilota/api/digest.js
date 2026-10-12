// Vercel Serverless Function (gratis). Legge Gmail + Calendar e prepara risposte con Gemini.
const J=async(u,o)=>{const r=await fetch(u,o);if(!r.ok)throw new Error(u.split('?')[0]+' '+r.status);return r.json()};
export default async function handler(req,res){
  if(req.query.k!==process.env.APP_SECRET)return res.status(401).json({error:'unauthorized'});
  try{
    const t=await J('https://oauth2.googleapis.com/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body:new URLSearchParams({client_id:process.env.G_CLIENT_ID,client_secret:process.env.G_CLIENT_SECRET,refresh_token:process.env.G_REFRESH_TOKEN,grant_type:'refresh_token'})});
    const H={headers:{Authorization:'Bearer '+t.access_token}};
    const now=new Date(),end=new Date(+now+30*36e5);
    let events=[];
    try{events=((await J(`https://www.googleapis.com/calendar/v3/calendars/primary/events?singleEvents=true&orderBy=startTime&maxResults=6&timeMin=${now.toISOString()}&timeMax=${end.toISOString()}`,H)).items||[])
      .map(e=>({title:e.summary||'(senza titolo)',start:e.start.dateTime||e.start.date,allDay:!e.start.dateTime,location:e.location||''}))}catch{} // facoltativo: il widget usa il Calendario nativo
    const ids=(await J('https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread%20in:inbox%20-category:promotions%20-category:social&maxResults=8',H)).messages||[];
    const mails=await Promise.all(ids.map(async m=>{
      const j=await J(`https://gmail.googleapis.com/gmail/v1/users/me/messages/${m.id}?format=metadata&metadataHeaders=From&metadataHeaders=Subject`,H);
      const h=n=>(j.payload.headers.find(x=>x.name===n)||{}).value||'';const from=h('From');
      return{id:m.id,from:from.replace(/<.*>/,'').trim()||from,email:(from.match(/<(.+)>/)||[,from])[1],subject:h('Subject'),snippet:j.snippet,priority:'media',why:'',draft:''}}));
    if(mails.length&&process.env.GEMINI_API_KEY){
      try{
        const g=await J(`https://generativelanguage.googleapis.com/v1beta/models/${process.env.GEMINI_MODEL||'gemini-2.5-flash'}:generateContent?key=${process.env.GEMINI_API_KEY}`,{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({contents:[{parts:[{text:`Sei l'assistente email di una persona italiana. Per ogni email rispondi JSON [{"i":0,"priority":"alta|media|bassa","why":"una riga su cosa serve","draft":"bozza di risposta breve, cortese, in prima persona, o stringa vuota se non serve rispondere"}]. Email: ${JSON.stringify(mails.map((m,i)=>({i,from:m.from,subject:m.subject,snippet:m.snippet})))}`}]}],generationConfig:{responseMimeType:'application/json',temperature:.3}})});
        JSON.parse(g.candidates[0].content.parts[0].text).forEach(x=>{if(mails[x.i])Object.assign(mails[x.i],{priority:x.priority,why:x.why,draft:x.draft})});
      }catch{}
    }
    const o={alta:0,media:1,bassa:2};mails.sort((a,b)=>o[a.priority]-o[b.priority]);
    res.setHeader('Cache-Control','s-maxage=300, stale-while-revalidate=600');
    res.status(200).json({generatedAt:now.toISOString(),events,mails});
  }catch(e){res.status(500).json({error:e.message})}
}
