import { Controller, Get, ServiceUnavailableException } from '@nestjs/common';
import { InjectConnection } from '@nestjs/mongoose';
import { Connection } from 'mongoose';
import { AppService } from './app.service';

@Controller()
export class AppController {
  constructor(
    private readonly appService: AppService,
    @InjectConnection() private readonly connection: Connection,
  ) {}

  @Get()
  getHello(): string {
    return this.appService.getHello();
  }

  @Get('health')
  getHealth() {
    return {
      status: 'ok',
      service: 'planitt-backend',
      timestamp: new Date().toISOString(),
    };
  }

  @Get('ready')
  getReady() {
    const connected = this.connection.readyState === 1;
    if (!connected) {
      throw new ServiceUnavailableException({
        status: 'not_ready',
        mongo_ready: false,
      });
    }
    return {
      status: 'ready',
      mongo_ready: true,
      timestamp: new Date().toISOString(),
    };
  }
}
