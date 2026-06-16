'use client';

import { useEffect, useRef } from 'react';
import styles from './SpaceBackground.module.css';

interface Star {
  x: number;
  y: number;
  r: number;
  baseOpacity: number;
  twinkleSpeed: number;
  phase: number;
}

export default function SpaceBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let stars: Star[] = [];
    let animId = 0;

    const buildStars = (w: number, h: number) => {
      // Reduce star count significantly for better performance
      const count = Math.min(250, Math.floor((w * h) / 6000)); 
      stars = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.5 + 0.2, // Slightly smaller variance
        baseOpacity: Math.random() * 0.7 + 0.2,
        twinkleSpeed: Math.random() * 0.0015 + 0.0005,
        phase: Math.random() * Math.PI * 2,
      }));
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = window.innerWidth;
      const h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      buildStars(w, h);
    };

    resize();
    window.addEventListener('resize', resize);

    const draw = (time: number) => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      ctx.clearRect(0, 0, w, h);

      ctx.fillStyle = '#e6f0ff'; // Use a solid fill style and change globalAlpha instead

      for (let i = 0; i < stars.length; i++) {
        const star = stars[i];
        // Simplified organic twinkle math
        const twinkle = 0.5 + 0.5 * Math.sin(time * star.twinkleSpeed + star.phase);
        ctx.globalAlpha = star.baseOpacity * twinkle;
        
        ctx.beginPath();
        ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
        ctx.fill();
        // Removed the expensive secondary glow arc pass for performance
      }

      ctx.globalAlpha = 1; // Reset alpha
      animId = requestAnimationFrame(draw);
    };

    animId = requestAnimationFrame(draw);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <div className={styles.space} aria-hidden="true">
      <canvas ref={canvasRef} className={styles.starsCanvas} />
      {/* Heavy animated blur elements commented out for performance */}
      {/* 
      <div className={styles.nebulaPurple} />
      <div className={styles.nebulaCyan} /> 
      */}
      <div className={styles.moon}>
        <div className={styles.moonGlow} />
        <div className={styles.moonBody}>
          <span className={styles.crater1} />
          <span className={styles.crater2} />
          <span className={styles.crater3} />
        </div>
      </div>
      {/* Astronaut image commented out per user request */}
      {/*
      <div className={styles.astronaut}>
        <img 
          src="/astronaut.png" 
          alt="Astronaut floating in space" 
          className={styles.astronautImg}
        />
      </div>
      */}
      <div className={styles.shootingStar} />
      <div className={styles.shootingStar2} />
    </div>
  );
}
