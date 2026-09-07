import { NextRequest } from "next/server";

const BACKEND_URL = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const API_KEY = process.env.PORTRAIT_API_KEY ?? "";

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const target = new URL(`${BACKEND_URL}/${path.join("/")}`);
  request.nextUrl.searchParams.forEach((value, key) => target.searchParams.append(key, value));

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  const requestId = request.headers.get("x-request-id");
  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  if (requestId) headers.set("x-request-id", requestId);
  if (API_KEY) headers.set("x-api-key", API_KEY);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: request.signal,
    });

    const responseHeaders = new Headers();
    const responseContentType = response.headers.get("content-type");
    const responseRequestId = response.headers.get("x-request-id");
    if (responseContentType) responseHeaders.set("content-type", responseContentType);
    if (responseRequestId) responseHeaders.set("x-request-id", responseRequestId);
    responseHeaders.set("cache-control", "no-store");

    return new Response(await response.arrayBuffer(), {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { detail: "Portrait backend is currently unavailable." },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
}

export const dynamic = "force-dynamic";

export function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
export function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxy(request, context);
}
