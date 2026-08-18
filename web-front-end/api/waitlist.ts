import { Resend } from 'resend';

interface WaitlistBody {
  name: string;
  email: string;
  role: string;
  firm: string;
  linkedin?: string;
}

const MAX_LENGTHS = { name: 100, email: 320, role: 100, firm: 200, linkedin: 2000 } as const;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// M10: this endpoint was unthrottled -- trivially scriptable, and each
// accepted submission spends a real Resend send. In-memory fixed window,
// per serverless instance rather than a shared store (no infra of its own
// here, unlike backend/security/rate_limiter.py's Supabase-backed limiter):
// good enough to stop casual scripting of a public marketing form, not a
// distributed guarantee. Upgrade to a shared store if abuse survives this.
const RATE_LIMIT_MAX_REQUESTS = 5;
const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const requestTimestampsByIp = new Map<string, number[]>();

export function isRateLimited(ip: string, now: number): boolean {
  const recent = (requestTimestampsByIp.get(ip) ?? []).filter(
    (ts) => now - ts < RATE_LIMIT_WINDOW_MS
  );
  recent.push(now);
  requestTimestampsByIp.set(ip, recent);
  return recent.length > RATE_LIMIT_MAX_REQUESTS;
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Rejects anything that isn't a well-formed https:// URL — used for both
 * validation and as the href, so a malformed value can never reach the DOM. */
export function parseHttpsUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.toString() : null;
  } catch {
    return null;
  }
}

export async function POST(request: Request) {
  try {
    const apiKey = process.env.RESEND_API_KEY;
    const notifyTo = process.env.AETHRIA_WAITLIST_NOTIFY_EMAIL;
    if (!apiKey || !notifyTo) {
      return Response.json(
        { detail: 'Email service not configured' },
        { status: 503 }
      );
    }

    const ip = request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() || 'unknown';
    if (isRateLimited(ip, Date.now())) {
      return Response.json({ detail: 'Too many requests, please try again later' }, { status: 429 });
    }

    const resend = new Resend(apiKey);
    const body = (await request.json()) as WaitlistBody;
    const name = (body.name ?? '').trim();
    const email = (body.email ?? '').trim();
    const role = (body.role ?? '').trim();
    const firm = (body.firm ?? '').trim();
    const linkedinRaw = (body.linkedin ?? '').trim();

    if (!name || !email || !role || !firm) {
      return Response.json(
        { detail: 'Name, email, role, and firm are required' },
        { status: 400 }
      );
    }
    if (
      name.length > MAX_LENGTHS.name ||
      email.length > MAX_LENGTHS.email ||
      role.length > MAX_LENGTHS.role ||
      firm.length > MAX_LENGTHS.firm ||
      linkedinRaw.length > MAX_LENGTHS.linkedin
    ) {
      return Response.json({ detail: 'One or more fields is too long' }, { status: 400 });
    }
    if (!EMAIL_REGEX.test(email)) {
      return Response.json(
        { detail: 'Please enter a valid email address' },
        { status: 400 }
      );
    }
    let linkedin: string | null = null;
    if (linkedinRaw) {
      linkedin = parseHttpsUrl(linkedinRaw);
      if (!linkedin) {
        return Response.json(
          { detail: 'LinkedIn must be a valid https:// URL' },
          { status: 400 }
        );
      }
    }

    const linkedinLine = linkedin
      ? `<li>LinkedIn: <a href="${escapeHtml(linkedin)}">${escapeHtml(linkedin)}</a></li>`
      : '';
    const html = `
      <p><strong>New early access signup</strong></p>
      <ul>
        <li>Name: ${escapeHtml(name)}</li>
        <li>Email: ${escapeHtml(email)}</li>
        <li>Role: ${escapeHtml(role)}</li>
        <li>Firm: ${escapeHtml(firm)}</li>
        ${linkedinLine}
      </ul>
    `;

    const { error } = await resend.emails.send({
      from: 'Aethria <early_access@mail.aethria.co>',
      to: [notifyTo],
      subject: `Early access request: ${name} (${firm})`,
      html,
    });

    if (error) {
      return Response.json({ detail: 'Failed to record request' }, { status: 502 });
    }

    return Response.json({ ok: true }, { status: 200 });
  } catch {
    return Response.json({ detail: 'Failed to record request' }, { status: 500 });
  }
}
