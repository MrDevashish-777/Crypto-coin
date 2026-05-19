import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { SignalsController } from './signals.controller';
import { SignalsService } from './signals.service';
import { Signal, SignalSchema } from './signal.schema';

@Module({
  imports: [MongooseModule.forFeature([{ name: Signal.name, schema: SignalSchema }])],
  controllers: [SignalsController],
  providers: [SignalsService],
})
export class SignalsModule {}

