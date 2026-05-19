import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const nodeEnv = process.env.NODE_ENV ?? 'development';
  const corsOriginsRaw = process.env.CORS_ORIGINS ?? '';
  const corsOrigins = corsOriginsRaw
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

  if (nodeEnv === 'production' && corsOrigins.length === 0) {
    throw new Error('CORS_ORIGINS must be set in production');
  }

  app.enableCors({
    origin:
      corsOrigins.length > 0
        ? (origin, callback) => {
            if (!origin || corsOrigins.includes(origin)) {
              callback(null, true);
              return;
            }
            callback(new Error('CORS origin not allowed'));
          }
        : true,
    credentials: true,
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Authorization', 'Content-Type', 'x-api-key', 'x-correlation-id'],
  });
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  if (nodeEnv === 'production' && !process.env.JWT_SECRET) {
    throw new Error('JWT_SECRET must be set in production');
  }

  await app.listen(process.env.PORT ?? 3000);
}
bootstrap();
