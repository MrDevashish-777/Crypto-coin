import { IsNumber, Min } from 'class-validator';

export class TakeProfitDto {
  @IsNumber()
  @Min(0)
  tp1: number;

  @IsNumber()
  @Min(0)
  tp2: number;

  @IsNumber()
  @Min(0)
  tp3: number;
}

