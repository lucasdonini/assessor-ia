// Synthetic contract subset from https://docs.typesafe.ai/api/system-one.
// Paths select a deterministic outcome; this does not simulate model accuracy.
const http = require('http');
const reply = (res, status, body) => {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(body));
};
http.createServer(async (req, res) => {
  const match = req.url.match(/^\/(approve|reject|partial|low|malformed|rate|error|hang)\/v1\/systemone$/);
  if (req.method !== 'POST' || !match) return reply(res, 501, {});
  const body = req.body;
  if (!body?.model || !body?.state || body.questions?.veredito?.type !== 'choice' ||
      body.questions?.apoiada?.type !== 'noul') return reply(res, 422, {});
  if (!req.headers.authorization?.startsWith('Bearer ')) return reply(res, 401, {});
  const mode = match[1];
  if (mode === 'rate') return reply(res, 429, {error: 'synthetic rate limit'});
  if (mode === 'error') return reply(res, 500, {error: 'synthetic failure'});
  if (mode === 'hang') await new Promise(resolve => setTimeout(resolve, 6000));
  if (mode === 'malformed') return reply(res, 200, {answers: {}});
  return reply(res, 200, {
    model: 'jev-1.14.0', answers: {
      veredito: {type: 'choice', choice: mode === 'reject' ? 'sem_apoio' : mode === 'partial' ? 'parcial' : 'apoiada'},
      apoiada: {type: 'noul', noul: mode === 'low' ? 0.69 : 0.91},
    }, usage: {input_tokens: 80, output_tokens: 2},
  });
}).listen(process.env.PORT || 4501);
