'use client'

import { SplineScene } from "@/components/ui/splite";
import { Card } from "@/components/ui/card"
import { Spotlight } from "@/components/ui/spotlight"
 
export function HeroSpline() {
  return (
    <Card 
      className="w-full min-h-[400px] md:h-[500px] bg-[rgba(10,15,30,0.8)] backdrop-blur-md relative overflow-hidden border border-[rgba(34,211,238,0.2)] rounded-[2.5rem] shadow-[0_8px_32px_rgba(0,0,0,0.6)] flex flex-col items-center justify-center transform-gpu"
      style={{ marginBottom: '5rem' }}
    >
      <Spotlight
        className="-top-40 left-0 md:left-1/2 md:-translate-x-1/2 md:-top-32"
        fill="rgba(34, 211, 238, 0.25)"
      />
      
      {/* Centered content */}
      <div 
        className="w-full max-w-4xl relative z-10 flex flex-col items-center justify-center text-center"
        style={{ padding: 'clamp(2rem, 5vw, 4rem)' }}
      >
        {/* Tech Accent Top */}
        <div className="flex items-center justify-center gap-3 mb-8 opacity-80">
          <div className="flex gap-1.5">
            <span className="w-1 h-4 bg-cyan-400 rounded-sm animate-pulse" />
            <span className="w-1 h-4 bg-cyan-400/40 rounded-sm" />
            <span className="w-1 h-4 bg-cyan-400/20 rounded-sm" />
          </div>
          <span className="text-[0.65rem] font-mono tracking-[0.3em] text-cyan-200/80 uppercase">
            Nebula Protocol // V2.0.4
          </span>
        </div>
        
        <h1 className="heroTitle" style={{ textAlign: 'center', marginBottom: '1.25rem', lineHeight: '1.05', letterSpacing: '-0.02em', fontSize: 'clamp(3rem, 5vw, 4.5rem)' }}>
          <span style={{ fontWeight: 400, color: '#f8fafc' }}>Trade with</span><br />
          <span className="textGlow" style={{ fontWeight: 800 }}>Algorithmic</span>
          <span style={{ fontWeight: 300, color: 'rgba(255,255,255,0.7)' }}> Clarity</span>
        </h1>
        
        <div style={{ marginBottom: '3rem' }}>
          <p className="heroSubtitle" style={{ 
            textAlign: 'center', 
            maxWidth: '600px', 
            margin: '0 auto',
            lineHeight: '1.7', 
            color: 'rgba(255, 255, 255, 0.65)', 
            fontSize: '1.1rem',
            fontWeight: 300
          }}>
            Cut through the noise of the crypto cosmos. Receive deeply vetted, high-probability trade setups straight from our quantitative models.
          </p>
        </div>

        {/* Call to Action Actions */}
        <div className="flex items-center justify-center gap-6" style={{ flexWrap: 'wrap' }}>
          <button 
            className="group relative overflow-hidden rounded-full font-medium tracking-wide text-sm transition-all duration-300"
            style={{ 
              padding: '0.9rem 2.2rem', 
              background: 'linear-gradient(135deg, #0ea5e9, #8b5cf6)',
              color: 'white',
              boxShadow: '0 8px 25px rgba(14, 165, 233, 0.25)',
              border: '1px solid rgba(255,255,255,0.1)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            Initialize Scan
          </button>
          
          <div 
            className="flex items-center gap-2.5"
            style={{ 
              padding: '0.55rem 1.25rem', 
              background: 'rgba(255,255,255,0.03)', 
              border: '1px solid rgba(255,255,255,0.08)',
              borderRadius: '999px',
              backdropFilter: 'blur(10px)'
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" style={{ boxShadow: '0 0 10px rgba(52,211,153,0.6)' }} />
            <span className="text-xs font-semibold" style={{ color: 'rgba(255,255,255,0.6)', letterSpacing: '0.05em' }}>STATUS OPTIMAL</span>
          </div>
        </div>
      </div>

      {/* Right content - 3D Robot (Commented out for performance) */}
      {/* 
      <div className="w-full md:w-[55%] relative min-h-[400px] md:h-full flex items-center justify-center">
        <SplineScene 
          scene="https://prod.spline.design/kZDDjO5HuC9GJUM2/scene.splinecode"
          className="w-full h-full"
        />
      </div>
      */}
    </Card>
  )
}
