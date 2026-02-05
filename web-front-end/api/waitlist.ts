import { Resend } from 'resend';

interface WaitlistBody {
  name: string;
  email: string;
  role: string;
  firm: string;
  linkedin: string;
}

export async function POST(request: Request) {
  try {
    const apiKey = process.env.RESEND_API_KEY;
    if (!apiKey) {
      return Response.json(
        { detail: 'Email service not configured' },
        { status: 503 }
      );
    }

    const resend = new Resend(apiKey);
    const body = (await request.json()) as WaitlistBody;
    const { name, email, role, firm, linkedin } = body;

    if (!name?.trim() || !email?.trim() || !role?.trim() || !firm?.trim() || !linkedin?.trim()) {
      return Response.json(
        { detail: 'Name, email, role, firm, and LinkedIn are required' },
        { status: 400 }
      );
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      return Response.json(
        { detail: 'Please enter a valid email address' },
        { status: 400 }
      );
    }

    const notifyTo =
      process.env.AETHRIA_WAITLIST_NOTIFY_EMAIL ?? 'delivered@resend.dev';
    const linkedinLine = `<li>LinkedIn: <a href="${linkedin.trim()}">${linkedin.trim()}</a></li>`;
    const html = `
      <p><strong>New early access signup</strong></p>
      <ul>
        <li>Name: ${name.trim()}</li>
        <li>Email: ${email.trim()}</li>
        <li>Role: ${role.trim()}</li>
        <li>Firm: ${firm.trim()}</li>
        ${linkedinLine}
      </ul>
    `;

    const { data, error } = await resend.emails.send({
      from: 'Aethria <early_access@mail.aethria.co>',
      to: [notifyTo],
      subject: `Early access request: ${name.trim()} (${firm.trim()})`,
      html,
    });

    if (error) {
      return Response.json(
        { detail: error.message || 'Failed to send email' },
        { status: 502 }
      );
    }

    return Response.json({ ok: true, id: data?.id }, { status: 200 });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : 'Something went wrong';
    return Response.json(
      { detail: `Failed to send: ${message}` },
      { status: 500 }
    );
  }
}
