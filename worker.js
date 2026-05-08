// Cloudflare Worker — SPPU Result Proxy
// Using HTTP because SPPU's SSL cert has incomplete chain (526 error)
const SPPU = 'http://onlineresults.unipune.ac.in';
let sppuCookie = '';

async function handleRequest(request) {
  const url = new URL(request.url);
  const path = url.pathname;

  const cors = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
  };

  if (request.method === 'OPTIONS') return new Response(null, { headers: cors });

  try {
    if (path === '/api/sessions') {
      const r = await fetch(`${SPPU}/Result/Dashboard/GetSession`, { headers: h() });
      saveCookie(r);
      const text = await r.text();
      let d;
      try { d = JSON.parse(text); } catch (e) { return errResponse('SPPU returned non-JSON for sessions', r.status, text, cors); }
      return jsonResponse(d, cors);
    }

    if (path === '/api/courses') {
      const period = url.searchParams.get('period');
      let target = `${SPPU}/Result/Dashboard/Default`;
      if (period) target += `?Exam_Period=${period}`;
      const r = await fetch(target, { headers: h() });
      saveCookie(r);
      const html = await r.text();
      return jsonResponse({ html }, cors);
    }

    if (path === '/api/captcha') {
      const r = await fetch(`${SPPU}/Result/Dashboard/RFCTLN`, {
        method: 'POST',
        headers: h(),
      });
      saveCookie(r);
      const text = await r.text();
      let d;
      try { d = JSON.parse(text); } catch (e) { return errResponse('SPPU returned non-JSON for captcha', r.status, text, cors); }
      return jsonResponse(d, cors);
    }

    if (path === '/api/result') {
      const fd = await request.formData();
      const params = new URLSearchParams();
      for (const [k, v] of fd.entries()) params.append(k, v.toString());
      const r = await fetch(`${SPPU}/SPPU%20ONLINE%20RESULT%20DISPLAY`, {
        method: 'POST',
        headers: { ...h(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString(),
      });
      const ct = r.headers.get('Content-Type') || 'application/pdf';
      const cd = r.headers.get('Content-Disposition') || '';
      const buf = await r.arrayBuffer();
      return new Response(buf, {
        headers: { 'Content-Type': ct, 'Content-Disposition': cd, 'Access-Control-Allow-Origin': '*' },
      });
    }

    return new Response('Not Found', { status: 404 });
  } catch (err) {
    return errResponse(err.message, 500, '', cors);
  }
}

function h() {
  const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': `${SPPU}/Result/Dashboard/Default`,
    'X-Requested-With': 'XMLHttpRequest',
  };
  if (sppuCookie) headers['Cookie'] = sppuCookie;
  return headers;
}

function saveCookie(r) {
  const sc = r.headers.get('Set-Cookie');
  if (sc) {
    const p = sc.split(';')[0];
    if (p.includes('=')) sppuCookie = p;
  }
}

function jsonResponse(data, cors) {
  return new Response(JSON.stringify(data), { headers: { ...cors, 'Content-Type': 'application/json' } });
}

function errResponse(msg, status, body, cors) {
  return new Response(JSON.stringify({ error: msg, status, snippet: body.substring(0, 200) }), {
    status: 500, headers: { ...cors, 'Content-Type': 'application/json' },
  });
}

export default { fetch: handleRequest };
