import { NextResponse } from 'next/server';
import clientPromise from '../../../lib/mongodb';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const client = await clientPromise;
    const dbName = process.env.MONGODB_DB_NAME || 'CryptoCoins';
    const collectionName = process.env.MONGODB_COLLECTION || 'signals';
    const db = client.db(dbName);
    const collection = db.collection(collectionName);

    // Fetch signals sorted by generated_at descending
    const signals = await collection
      .find({})
      .sort({ generated_at: -1 })
      .limit(150)
      .toArray();

    return NextResponse.json({ signals });
  } catch (error) {
    console.error('Failed to fetch signals', error);
    return NextResponse.json({ error: 'Failed to fetch signals' }, { status: 500 });
  }
}
