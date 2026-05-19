import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Request } from 'express';

@Injectable()
export class ApiKeyGuard implements CanActivate {
  constructor(private readonly cfg: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest<Request & { headers: Record<string, string> }>();
    const xApiKey = req.headers['x-api-key'];
    const expected = this.cfg.get<string>('PLANITT_INTERNAL_API_KEY');

    if (!expected) {
      throw new UnauthorizedException('Internal API key not configured');
    }
    if (!xApiKey || xApiKey !== expected) {
      throw new UnauthorizedException('Invalid internal API key');
    }
    return true;
  }
}

