// Contract subset: official MCP create_event and REST events.insert. Synthetic data only.
const http = require('http');
const json = (res, status, body) => {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(body));
};
http.createServer(async (req, res) => {
  const path = req.url.split('?')[0];
  const records = (await pm.state.get('google-calendar:events')) || [];
  if (req.method === 'GET' && path === '/records') return json(res, 200, records);
  if (req.method === 'DELETE' && path === '/records') {
    await pm.state.set('google-calendar:events', []); return json(res, 200, {});
  }
  if (req.method === 'POST' && path === '/calendars/primary/events') {
    const event = req.body;
    if (!event.summary || !event.start?.dateTime || !event.end?.dateTime) return json(res, 400, {});
    const saved = { ...event, id: `rest-${records.length + 1}` };
    records.push(saved); await pm.state.set('google-calendar:events', records);
    return json(res, 200, saved);
  }
  if (req.method === 'GET' && path.startsWith('/mcp/')) return json(res, 405, {});
  if (req.method !== 'POST' || !path.startsWith('/mcp/')) return json(res, 501, {});
  const mode = path.split('/')[2];
  if (mode === 'disabled') return json(res, 403, { error: { code: 403, details: [{
    '@type': 'type.googleapis.com/google.rpc.ErrorInfo', reason: 'SERVICE_DISABLED',
    domain: 'googleapis.com', metadata: { service: 'calendarmcp.googleapis.com' },
  }] } });
  if (mode === 'denied') return json(res, 403, { error: { code: 403, message: 'Permission denied' } });
  const body = req.body || {};
  if (body.id === undefined) { res.writeHead(202); return res.end(); }
  let result;
  if (body.method === 'initialize') {
    result = { protocolVersion: body.params.protocolVersion, capabilities: { tools: {} },
      serverInfo: { name: 'synthetic-calendar', version: '1.0.0' } };
  } else if (body.method === 'tools/list') {
    result = { tools: [{ name: 'create_event', description: 'Create event', inputSchema: {
      type: 'object', properties: { summary: { type: 'string' }, startTime: { type: 'string' },
        endTime: { type: 'string' }, calendarId: { type: 'string' }, timeZone: { type: 'string' },
        location: { type: 'string' }, description: { type: 'string' } },
      required: ['summary', 'startTime', 'endTime'],
    } }] };
  } else if (body.method === 'tools/call' && body.params.name === 'create_event') {
    const event = body.params.arguments;
    if (!event.summary || !event.startTime || !event.endTime) return json(res, 400, {});
    if (mode === 'preview-required') result = { content: [{ type: 'text', text: 'Access to this tool requires that your Google Cloud project is enrolled in the Google Workspace Developer Preview Program.' }], isError: true };
    else if (mode === 'tool-error') result = { content: [{ type: 'text', text: 'Rejected' }], isError: true };
    else {
      const saved = { ...event, id: `mcp-${records.length + 1}` };
      records.push(saved); await pm.state.set('google-calendar:events', records);
      if (mode === 'server-error') return json(res, 500, { error: 'Uncertain result' });
      if (mode === 'hanging') await new Promise(resolve => setTimeout(resolve, 35000));
      result = { content: [{ type: 'text', text: JSON.stringify(saved) }], structuredContent: saved };
    }
  } else return json(res, 501, {});
  return json(res, 200, { jsonrpc: '2.0', id: body.id, result });
}).listen(process.env.PORT || 4500);
