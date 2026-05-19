import { IsObject, IsOptional, IsString } from 'class-validator';

export class UpsertMarketStatusDto {
  @IsObject()
  payload: Record<string, unknown>;

  @IsOptional()
  @IsString()
  observed_at?: string;
}
