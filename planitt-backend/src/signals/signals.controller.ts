import { Body, Controller, Get, Headers, HttpCode, Param, Post, Query, UseGuards } from '@nestjs/common';
import { CreateSignalDto } from './dto/create-signal.dto';
import { SignalsService } from './signals.service';
import { ApiKeyGuard } from '../common/guards/api-key.guard';

@Controller()
export class SignalsController {
  constructor(private readonly signalsService: SignalsService) {}

  // Internal endpoint: trusted service-to-service write
  @Post('signals')
  @UseGuards(ApiKeyGuard)
  @HttpCode(201)
  async createInternal(
    @Body() dto: CreateSignalDto,
    @Headers('x-correlation-id') correlationId?: string,
  ) {
    // Status can be overwritten by backend later as trade outcomes are tracked.
    return this.signalsService.createInternal(dto, correlationId);
  }

  // Public endpoints: read-only for frontend/mobile
  @Get('signals')
  @UseGuards(ApiKeyGuard)
  async getSignals(
    @Query('asset') asset?: string,
    @Query('timeframe') timeframe?: string,
    @Query('limit') limit?: string,
    @Headers('x-correlation-id') correlationId?: string,
  ) {
    const parsedLimit = limit ? parseInt(limit, 10) : undefined;
    return this.signalsService.getActiveSignals({ asset, timeframe, limit: parsedLimit }, correlationId);
  }

  @Get('signals/:id')
  @UseGuards(ApiKeyGuard)
  async getSignalById(@Param('id') id: string) {
    return this.signalsService.getByIdPublic(id);
  }

  @Get('performance')
  @UseGuards(ApiKeyGuard)
  async getPerformance() {
    return this.signalsService.getPerformance();
  }

  // Internal read endpoints for trusted admin tools (avoid manual JWT generation in ops)
  @Get('internal/signals')
  @UseGuards(ApiKeyGuard)
  async getSignalsInternal(
    @Query('asset') asset?: string,
    @Query('timeframe') timeframe?: string,
    @Query('limit') limit?: string,
    @Headers('x-correlation-id') correlationId?: string,
  ) {
    const parsedLimit = limit ? parseInt(limit, 10) : undefined;
    return this.signalsService.getActiveSignals({ asset, timeframe, limit: parsedLimit }, correlationId);
  }

  @Get('internal/performance')
  @UseGuards(ApiKeyGuard)
  async getPerformanceInternal() {
    return this.signalsService.getPerformance();
  }

  @Get('internal/signals/:id')
  @UseGuards(ApiKeyGuard)
  async getSignalByIdInternal(@Param('id') id: string) {
    return this.signalsService.getByIdPublic(id);
  }
}

