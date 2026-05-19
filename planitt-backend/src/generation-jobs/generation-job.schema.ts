import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

export type GenerationJobDocument = HydratedDocument<GenerationJob>;

export type GenerationJobStatus = 'pending' | 'processing' | 'completed' | 'failed';

@Schema({ collection: 'generation_jobs', timestamps: true })
export class GenerationJob {
  @Prop({ required: true, index: true })
  symbol: string;

  @Prop({ required: true, index: true })
  timeframe: string;

  @Prop({ required: true, default: 'planitt' })
  strategy: string;

  @Prop({ required: true, index: true, default: 'pending' })
  status: GenerationJobStatus;

  @Prop({ type: Date, index: true })
  leased_until?: Date;

  @Prop()
  worker_id?: string;

  @Prop({ type: Object })
  result?: Record<string, unknown>;

  @Prop()
  error?: string;

  @Prop({ type: Date })
  completed_at?: Date;
}

export const GenerationJobSchema = SchemaFactory.createForClass(GenerationJob);
GenerationJobSchema.index({ status: 1, createdAt: 1 });
