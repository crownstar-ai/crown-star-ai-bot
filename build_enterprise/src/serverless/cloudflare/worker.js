// serverless/cloudflare/worker.js – Cloudflare Worker that proxies to CrownStar API
// For production, would use Workers AI or call external API
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    
    // Health check
    if (url.pathname === "/health") {
      return new Response(JSON.stringify({ status: "ok", version: "7.0.1" }), {
        headers: { "Content-Type": "application/json" }
      });
    }
    
    // Only POST /v1/chat is implemented
    if (url.pathname === "/v1/chat" && request.method === "POST") {
      try {
        const body = await request.json();
        const query = body.query || "";
        
        // Option A: Call backend CrownStar API (if deployed elsewhere)
        // const backendUrl = env.BACKEND_URL || "https://api.crownstar.ai";
        // const resp = await fetch(`${backendUrl}/v1/chat`, {
        //   method: "POST",
        //   headers: { "Content-Type": "application/json" },
        //   body: JSON.stringify(body)
        // });
        // return resp;
        
        // Option B: Simplified edge response (for demo)
        const answer = `Edge response to: ${query} (Cloudflare Worker)`;
        return new Response(JSON.stringify({ answer, source: "cloudflare-worker" }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ error: err.message }), { status: 500 });
      }
    }
    
    return new Response("Not found", { status: 404 });
  }
};
