import { ConflictException, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { createHash } from 'crypto';
import { CreateSignalDto } from './dto/create-signal.dto';
import { Signal } from './signal.schema';

function validityToMaxTtlSeconds(validity: string | undefined): number | null {
  if (!validity) return null;
  const v = validity.toLowerCase().trim();

  // Examples: "2-4 hours", "30-90 minutes"
  const range = v.match(/(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(hour|hours|minute|minutes|day|days)/i);
  if (range) {
    const maxVal = parseFloat(range[2]);
    const unit = range[3].toLowerCase();
    if (unit.startsWith('hour')) return Math.round(maxVal * 3600);
    if (unit.startsWith('minute')) return Math.round(maxVal * 60);
    if (unit.startsWith('day')) return Math.round(maxVal * 86400);
  }

  const single = v.match(/(\d+(?:\.\d+)?)\s*(hour|hours|minute|minutes|day|days)/i);
  if (single) {
    const val = parseFloat(single[1]);
    const unit = single[2].toLowerCase();
    if (unit.startsWith('hour')) return Math.round(val * 3600);
    if (unit.startsWith('minute')) return Math.round(val * 60);
    if (unit.startsWith('day')) return Math.round(val * 86400);
  }

  return null;
}

@Injectable()
export class SignalsService {
  private readonly logger = new Logger(SignalsService.name);

  constructor(@InjectModel(Signal.name) private readonly signalModel: Model<Signal>) {}

  async createInternal(dto: CreateSignalDto, correlationId?: string): Promise<Signal> {
    const createdAt = new Date(dto.created_at);
    const timestamp = createdAt.toISOString();

    // Convert exchange pair -> base asset (matches `BTCUSDT` -> `BTC`)
    const assetUpper = typeof dto.asset === 'string' ? dto.asset.toUpperCase() : dto.asset;
    const symbol = typeof assetUpper === 'string' ? assetUpper.replace(/USDT$/, '') : assetUpper;

    const entryLow = dto.entry_range[0];
    const entryHigh = dto.entry_range[1];
    const entry_price = (entryLow + entryHigh) / 2;
    const target_price = dto.take_profit.tp2;

    // Processor confidence is 1..100; apps expect confidence_score in 0..1 range.
    const confidence_score = dto.confidence / 100;

    const idempotency_key =
      dto.dedup_key ??
      createHash('sha256')
        .update(`${dto.asset}|${dto.timeframe}|${timestamp}`)
        .digest('hex');

    const input: Record<string, unknown> = {
      // Raw fields (existing)
      asset: dto.asset,
      signal_type: dto.signal_type,
      entry_range: dto.entry_range,
      stop_loss: dto.stop_loss,
      take_profit: dto.take_profit,
      timeframe: dto.timeframe,
      confidence: dto.confidence,
      strategy: dto.strategy,
      reason: dto.reason,
      validity: dto.validity,
      created_at: createdAt,
      status: dto.status,
      risk_reward_ratio: dto.risk_reward_ratio,

      // Unified fields (Gateway + apps expect these)
      symbol,
      display_name: typeof symbol === 'string' ? symbol : dto.asset,
      asset_class: 'CRYPTO',
      source_backend: 'crypto_bot',
      entry_price,
      target_price,
      confidence_score,
      timestamp,
      idempotency_key,
      is_published: false,
      research_status: 'pending',
    };
    if (dto.dedup_key) input.dedup_key = dto.dedup_key;
    if (dto.expires_at) {
      input.expires_at = new Date(dto.expires_at);
    } else if (dto.validity && dto.created_at) {
      const ttlSeconds = validityToMaxTtlSeconds(dto.validity);
      if (ttlSeconds && ttlSeconds > 0) {
        const createdAt = new Date(dto.created_at);
        input.expires_at = new Date(createdAt.getTime() + ttlSeconds * 1000);
      }
    }

    if (dto.dedup_key) {
      try {
        const doc = await this.signalModel
          .findOneAndUpdate({ dedup_key: dto.dedup_key }, { $set: input }, { upsert: true, new: true, runValidators: true })
          .exec();
        if (!doc) {
          throw new Error('Upsert returned no document');
        }
        this.logger.log(
          JSON.stringify({
            event: 'signal_upserted',
            correlation_id: correlationId,
            asset: dto.asset,
            timeframe: dto.timeframe,
            status: doc.status,
            signal_type: dto.signal_type,
            dedup_key: dto.dedup_key,
          }),
        );
        return doc;
      } catch (e: any) {
        this.logger.error(
          JSON.stringify({
            event: 'signal_upsert_failed',
            correlation_id: correlationId,
            asset: dto.asset,
            timeframe: dto.timeframe,
            error: e?.message ?? String(e),
          }),
        );
        throw e;
      }
    }

    try {
      const created = new this.signalModel(input);
      const saved = await created.save();

      this.logger.log(
        JSON.stringify({
          event: 'signal_inserted',
          correlation_id: correlationId,
          asset: dto.asset,
          timeframe: dto.timeframe,
          status: saved.status,
          signal_type: dto.signal_type,
        }),
      );

      return saved;
    } catch (e: any) {
      if (e?.code === 11000) {
        this.logger.warn(
          JSON.stringify({
            event: 'signal_duplicate_deduped',
            correlation_id: correlationId,
            asset: dto.asset,
            timeframe: dto.timeframe,
          }),
        );
        throw new ConflictException('Duplicate signal (dedup_key)');
      }
      this.logger.error(
        JSON.stringify({
          event: 'signal_insert_failed',
          correlation_id: correlationId,
          asset: dto.asset,
          timeframe: dto.timeframe,
          error: e?.message ?? String(e),
        }),
      );
      throw e;
    }
  }

  async getActiveSignals(query: { asset?: string; timeframe?: string; limit?: number }, correlationId?: string): Promise<any[]> {
    const now = new Date();
    const limit = Math.min(Math.max(query.limit ?? 50, 1), 200);

    // Update status for expired signals so consumers see consistent state.
    const updateRes = await this.signalModel.updateMany(
      { status: 'active', expires_at: { $lte: now } },
      { $set: { status: 'expired' } },
    );
    if (updateRes && updateRes.modifiedCount && updateRes.modifiedCount > 0) {
      this.logger.log(
        JSON.stringify({
          event: 'signals_expired_marked',
          correlation_id: correlationId,
          modified_count: updateRes.modifiedCount,
        }),
      );
    }

    const filter: any = {
      status: 'active',
      is_published: true,
      $or: [{ expires_at: { $gt: now } }, { expires_at: { $exists: false } }, { expires_at: null }],
    };

    if (query.asset) filter.asset = query.asset;
    if (query.timeframe) filter.timeframe = query.timeframe;

    return this.signalModel
      .find(filter)
      .sort({ created_at: -1 })
      .limit(limit)
      .lean()
      .exec();
  }

  async getByIdPublic(id: string): Promise<any> {
    const now = new Date();

    await this.signalModel.updateMany(
      { status: 'active', expires_at: { $lte: now } },
      { $set: { status: 'expired' } },
    );

    const doc = await this.signalModel.findOne({
      _id: id,
      status: 'active',
      is_published: true,
      $or: [{ expires_at: { $gt: now } }, { expires_at: { $exists: false } }, { expires_at: null }],
    });

    if (!doc) throw new NotFoundException('Signal not found');
    return doc;
  }

  async getPerformance(): Promise<any> {
    // Lightweight placeholder until execution tracking exists.
    const total = await this.signalModel.countDocuments().exec();
    const active = await this.signalModel.countDocuments({ status: 'active' }).exec();
    return { total, active };
  }
}

