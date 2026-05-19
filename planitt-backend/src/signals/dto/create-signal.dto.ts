import {
  ArrayMaxSize,
  ArrayMinSize,
  IsArray,
  IsDateString,
  IsEnum,
  IsInt,
  IsNumber,
  IsOptional,
  IsString,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';
import { TakeProfitDto } from './take-profit.dto';

export type SignalType = 'BUY' | 'SELL';

export class CreateSignalDto {
  @IsString()
  asset: string;

  @IsEnum(['BUY', 'SELL'])
  signal_type: SignalType;

  @IsArray()
  @ArrayMinSize(2)
  @ArrayMaxSize(2)
  @IsNumber({}, { each: true })
  entry_range: number[];

  @IsNumber()
  stop_loss: number;

  @ValidateNested()
  @Type(() => TakeProfitDto)
  take_profit: TakeProfitDto;

  @IsString()
  timeframe: string;

  @IsInt()
  confidence: number;

  @IsString()
  strategy: string;

  @IsString()
  reason: string;

  @IsString()
  validity: string;

  @IsDateString()
  created_at: string;

  @IsString()
  status: 'active' | 'hit_tp' | 'hit_sl' | 'expired';

  @IsString()
  risk_reward_ratio: string;

  @IsOptional()
  @IsDateString()
  expires_at?: string;

  @IsOptional()
  @IsString()
  dedup_key?: string;
}

