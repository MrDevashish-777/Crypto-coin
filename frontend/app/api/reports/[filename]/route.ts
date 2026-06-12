import { NextRequest, NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  const { filename } = await params;
  const safeName = filename.replace(/[/\\]/g, '');
  if (!safeName || !safeName.endsWith('.pdf')) {
    return NextResponse.json({ error: 'Invalid filename' }, { status: 400 });
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  const backendUrl = `${apiBase}/api/v1/advisor/reports/${encodeURIComponent(safeName)}`;

  try {
    const res = await fetch(backendUrl);
    if (!res.ok) {
      return NextResponse.json({ error: 'Report not found' }, { status: res.status });
    }

    const pdfBuffer = await res.arrayBuffer();
    return new NextResponse(pdfBuffer, {
      status: 200,
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="${safeName}"`,
        'Cache-Control': 'private, max-age=3600',
      },
    });
  } catch (error) {
    console.error('PDF proxy fetch failed', error);
    return NextResponse.json({ error: 'Failed to fetch report' }, { status: 502 });
  }
}
