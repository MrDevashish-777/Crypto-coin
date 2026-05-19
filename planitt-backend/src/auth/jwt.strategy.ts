import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';

type JwtPayload = {
  sub?: string;
  username?: string;
  exp?: number;
  iat?: number;
};

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(private readonly cfg: ConfigService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      secretOrKey: cfg.get<string>('JWT_SECRET'),
      ignoreExpiration: false,
    });
  }

  async validate(payload: JwtPayload) {
    if (!payload?.sub) {
      throw new UnauthorizedException('Invalid JWT payload');
    }
    return payload;
  }
}

