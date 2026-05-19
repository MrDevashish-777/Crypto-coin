import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { NewsController } from './news.controller';
import { NewsService } from './news.service';
import { NewsItem, NewsItemSchema } from './news.schema';

@Module({
  imports: [MongooseModule.forFeature([{ name: NewsItem.name, schema: NewsItemSchema }])],
  controllers: [NewsController],
  providers: [NewsService],
})
export class NewsModule {}
