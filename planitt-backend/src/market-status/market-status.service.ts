import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { MarketStatus } from './market-status.schema';
import { UpsertMarketStatusDto } from './dto/upsert-market-status.dto';

@Injectable()
export class MarketStatusService {
  constructor(@InjectModel(MarketStatus.name) private readonly marketStatusModel: Model<MarketStatus>) {}

  async getLatest() {
    const latest = await this.marketStatusModel.findOne({ key: 'latest' }).lean().exec();
    return latest ?? { key: 'latest', payload: {}, observed_at: null };
  }

  async upsertLatest(dto: UpsertMarketStatusDto) {
    const observed_at = dto.observed_at ? new Date(dto.observed_at) : new Date();
    return this.marketStatusModel
      .findOneAndUpdate(
        { key: 'latest' },
        {
          $set: {
            key: 'latest',
            payload: dto.payload,
            observed_at,
          },
        },
        { upsert: true, new: true },
      )
      .lean()
      .exec();
  }
}
