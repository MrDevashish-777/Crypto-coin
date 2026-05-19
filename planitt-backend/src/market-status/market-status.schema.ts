import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type MarketStatusDocument = HydratedDocument<MarketStatus>;

@Schema({ collection: 'market_status', timestamps: true })
export class MarketStatus {
  @Prop({ required: true, unique: true, default: 'latest' })
  key: string;

  @Prop({ type: Object, required: true })
  payload: Record<string, unknown>;

  @Prop({ type: Date, required: true, index: true })
  observed_at: Date;
}

export const MarketStatusSchema = SchemaFactory.createForClass(MarketStatus);
