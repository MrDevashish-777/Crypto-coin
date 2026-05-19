import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { createHash } from 'crypto';
import { NewsItem } from './news.schema';
import { NewsInputDto } from './dto/upsert-news.dto';

function buildDedupKey(item: NewsInputDto): string {
  const base = `${item.url ?? ''}|${item.title}|${item.published_at ?? ''}`;
  return createHash('sha256').update(base).digest('hex');
}

@Injectable()
export class NewsService {
  constructor(@InjectModel(NewsItem.name) private readonly newsModel: Model<NewsItem>) {}

  async getNews(limit = 20) {
    const parsedLimit = Math.min(Math.max(limit, 1), 200);
    return this.newsModel.find({}).sort({ published_at: -1, createdAt: -1 }).limit(parsedLimit).lean().exec();
  }

  async upsertMany(items: NewsInputDto[]) {
    const ops = items.map((item) => {
      const dedup_key = buildDedupKey(item);
      return {
        updateOne: {
          filter: { dedup_key },
          update: {
            $set: {
              title: item.title,
              summary: item.summary,
              source: item.source,
              url: item.url,
              published_at: item.published_at ? new Date(item.published_at) : undefined,
              sentiment: item.sentiment,
              raw: item.raw,
              dedup_key,
            },
          },
          upsert: true,
        },
      };
    });
    if (ops.length === 0) return { upserted: 0 };
    const result = await this.newsModel.bulkWrite(ops, { ordered: false });
    return {
      matched: result.matchedCount,
      modified: result.modifiedCount,
      upserted: result.upsertedCount,
    };
  }
}
