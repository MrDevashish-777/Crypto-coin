import { Body, Controller, Get, Post, Query, UseGuards } from '@nestjs/common';
import { ApiKeyGuard } from '../common/guards/api-key.guard';
import { NewsService } from './news.service';
import { UpsertNewsDto } from './dto/upsert-news.dto';

@Controller()
export class NewsController {
  constructor(private readonly newsService: NewsService) {}

  @Get('news')
  @UseGuards(ApiKeyGuard)
  async getNews(@Query('limit') limit?: string) {
    const parsedLimit = limit ? parseInt(limit, 10) : 20;
    return this.newsService.getNews(parsedLimit);
  }

  @Post('internal/news')
  @UseGuards(ApiKeyGuard)
  async upsertNews(@Body() dto: UpsertNewsDto) {
    return this.newsService.upsertMany(dto.items ?? []);
  }
}
