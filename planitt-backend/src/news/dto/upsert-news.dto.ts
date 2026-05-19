import { IsArray, IsNotEmpty, IsObject, IsOptional, IsString, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';

export class NewsInputDto {
  @IsString()
  @IsNotEmpty()
  title: string;

  @IsOptional()
  @IsString()
  summary?: string;

  @IsOptional()
  @IsString()
  source?: string;

  @IsOptional()
  @IsString()
  url?: string;

  @IsOptional()
  @IsString()
  published_at?: string;

  @IsOptional()
  @IsObject()
  sentiment?: Record<string, unknown>;

  @IsOptional()
  @IsObject()
  raw?: Record<string, unknown>;
}

export class UpsertNewsDto {
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => NewsInputDto)
  items: NewsInputDto[];
}
