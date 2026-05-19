import { Body, Controller, Get, Post, UseGuards } from '@nestjs/common';
import { ApiKeyGuard } from '../common/guards/api-key.guard';
import { MarketStatusService } from './market-status.service';
import { UpsertMarketStatusDto } from './dto/upsert-market-status.dto';

@Controller()
export class MarketStatusController {
  constructor(private readonly marketStatusService: MarketStatusService) {}

  @Get('market-status')
  @UseGuards(ApiKeyGuard)
  async getLatest() {
    return this.marketStatusService.getLatest();
  }

  @Post('internal/market-status')
  @UseGuards(ApiKeyGuard)
  async upsertLatest(@Body() dto: UpsertMarketStatusDto) {
    return this.marketStatusService.upsertLatest(dto);
  }
}
