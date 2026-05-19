import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type NewsDocument = HydratedDocument<NewsItem>;

@Schema({ collection: 'news', timestamps: true })
export class NewsItem {
  @Prop({ required: true, index: true })
  title: string;

  @Prop()
  summary?: string;

  @Prop()
  source?: string;

  @Prop({ index: true })
  url?: string;

  @Prop({ type: Date, index: true })
  published_at?: Date;

  @Prop({ type: Object })
  sentiment?: Record<string, unknown>;

  @Prop({ type: Object })
  raw?: Record<string, unknown>;

  @Prop({ required: true, index: true })
  dedup_key: string;
}

export const NewsItemSchema = SchemaFactory.createForClass(NewsItem);
NewsItemSchema.index({ dedup_key: 1 }, { unique: true });
NewsItemSchema.index({ published_at: -1 });
