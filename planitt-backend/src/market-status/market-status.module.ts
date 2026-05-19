import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { MarketStatusController } from './market-status.controller';
import { MarketStatusService } from './market-status.service';
import { MarketStatus, MarketStatusSchema } from './market-status.schema';

@Module({
  imports: [MongooseModule.forFeature([{ name: MarketStatus.name, schema: MarketStatusSchema }])],
  controllers: [MarketStatusController],
  providers: [MarketStatusService],
})
export class MarketStatusModule {}
