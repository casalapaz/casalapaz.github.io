// Einstieg der Supabase Edge Function "push". Logik in handler.ts, Verschlüsselung in webpush.ts.
// Ausgespielt per GitHub-Workflow "Mitteilungen ausspielen" (.github/workflows/push.yml).
import { envDeps, handler } from "./handler.ts";

Deno.serve(handler(envDeps(Deno.env)));
