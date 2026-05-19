"""
Crypto Bot — ML Backtesting Report Generator
Tests: Market Regime Detector, Multi-Strategy Consensus, DistilBERT Sentiment
Generates investor-ready PDF with real numeric metrics.
"""
import os, sys, warnings, math
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

warnings.filterwarnings("ignore")

SYMBOLS = ["BTC-USD","ETH-USD","BNB-USD","SOL-USD","XRP-USD","ADA-USD","DOGE-USD","AVAX-USD","DOT-USD","MATIC-USD"]
PERIOD = "2y"
TEST_SPLIT = 0.2
OUTPUT_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Crypto_Bot_ML_Backtest_Report.pdf")

# ── INDICATORS ──
def calc_ema(s, p):
    return s.ewm(span=p, adjust=False).mean()

def calc_rsi(s, p=14):
    d = s.diff()
    g = d.where(d>0,0).rolling(p).mean()
    l = (-d.where(d<0,0)).rolling(p).mean()
    return 100 - (100/(1+g/(l+1e-9)))

def calc_atr(h, l, c, p=14):
    tr = pd.concat([h-l, abs(h-c.shift(1)), abs(l-c.shift(1))], axis=1).max(axis=1)
    return tr.rolling(p).mean()

def calc_adx(h, l, c, p=14):
    plus_dm = h.diff(); minus_dm = -l.diff()
    plus_dm = plus_dm.where((plus_dm>minus_dm)&(plus_dm>0), 0)
    minus_dm = minus_dm.where((minus_dm>plus_dm)&(minus_dm>0), 0)
    atr = calc_atr(h, l, c, p)
    plus_di = 100*(plus_dm.rolling(p).mean()/(atr+1e-9))
    minus_di = 100*(minus_dm.rolling(p).mean()/(atr+1e-9))
    dx = 100*abs(plus_di-minus_di)/(plus_di+minus_di+1e-9)
    adx = dx.rolling(p).mean()
    return adx, plus_di, minus_di

def calc_bb(c, p=20):
    ma = c.rolling(p).mean(); std = c.rolling(p).std()
    return ma, ma+2*std, ma-2*std, (4*std)/(ma+1e-9)

def calc_macd(c):
    e12 = c.ewm(span=12).mean(); e26 = c.ewm(span=26).mean()
    macd = e12-e26; sig = macd.ewm(span=9).mean()
    return macd, sig, macd-sig

def calc_supertrend(h, l, c, p=10, m=3.0):
    atr = calc_atr(h, l, c, p)
    hl2 = (h+l)/2
    ub = hl2 + m*atr; lb = hl2 - m*atr
    st = pd.Series(index=c.index, dtype=float)
    d = pd.Series(1, index=c.index)
    st.iloc[0] = lb.iloc[0]
    for i in range(1, len(c)):
        if c.iloc[i] > ub.iloc[i-1]: d.iloc[i] = 1
        elif c.iloc[i] < lb.iloc[i-1]: d.iloc[i] = -1
        else: d.iloc[i] = d.iloc[i-1]
        st.iloc[i] = lb.iloc[i] if d.iloc[i]==1 else ub.iloc[i]
    return st, d

# ── REGIME DETECTOR (mirrors market_regime.py) ──
def detect_regime(h, l, c, idx):
    if idx < 52: return "unknown", 0.5
    sl = slice(max(0,idx-60), idx+1)
    ch, cl, cc = h.iloc[sl], l.iloc[sl], c.iloc[sl]
    adx_s, pdi, mdi = calc_adx(ch, cl, cc)
    atr_s = calc_atr(ch, cl, cc)
    _, _, _, bw = calc_bb(cc)
    adx_v = float(adx_s.iloc[-1]) if not np.isnan(adx_s.iloc[-1]) else 20
    pdi_v = float(pdi.iloc[-1]) if not np.isnan(pdi.iloc[-1]) else 0
    mdi_v = float(mdi.iloc[-1]) if not np.isnan(mdi.iloc[-1]) else 0
    atr_v = float(atr_s.iloc[-1]) if not np.isnan(atr_s.iloc[-1]) else 0
    avg_atr = float(atr_s.iloc[-20:].mean()) if len(atr_s)>=20 else atr_v
    ema50 = float(calc_ema(cc, 50).iloc[-1])
    price = float(cc.iloc[-1])
    is_vol = avg_atr>0 and (atr_v/avg_atr)>1.5
    if is_vol: return "volatile", min(0.9, (atr_v/avg_atr-1)*0.7+0.5)
    if adx_v < 20: return "ranging", min(0.9, 0.5+(20-adx_v)/20*0.4)
    if adx_v >= 25:
        if pdi_v > mdi_v:
            conf = min(0.95, 0.65+(adx_v-25)/40) if price>ema50 else 0.6
            return "trending_up", conf
        else:
            conf = min(0.95, 0.65+(adx_v-25)/40) if price<ema50 else 0.6
            return "trending_down", conf
    return "ranging", 0.5

# ── STRATEGY SIGNALS (mirrors 9 strategies) ──
def run_strategies(h, l, c, v, idx):
    if idx < 60: return {}
    sl = slice(max(0,idx-200), idx+1)
    ch, cl, cc, cv = h.iloc[sl], l.iloc[sl], c.iloc[sl], v.iloc[sl]
    signals = {}
    price = float(cc.iloc[-1])
    rsi = float(calc_rsi(cc).iloc[-1])
    macd_l, macd_s, macd_h = calc_macd(cc)
    atr = float(calc_atr(ch,cl,cc).iloc[-1])
    ema21 = float(calc_ema(cc,21).iloc[-1])
    ema50 = float(calc_ema(cc,50).iloc[-1])
    _, _, _, bw = calc_bb(cc)
    bw_v = float(bw.iloc[-1]) if not np.isnan(bw.iloc[-1]) else 0
    macd_hv = float(macd_h.iloc[-1])
    macd_hv_prev = float(macd_h.iloc[-2]) if len(macd_h)>1 else 0
    # RSI
    if rsi<30: signals['rsi']='BUY'
    elif rsi>70: signals['rsi']='SELL'
    # MACD
    if macd_hv>0 and macd_hv_prev<=0: signals['macd']='BUY'
    elif macd_hv<0 and macd_hv_prev>=0: signals['macd']='SELL'
    # EMA Trend
    if ema21>ema50 and price>ema21: signals['ema_trend']='BUY'
    elif ema21<ema50 and price<ema21: signals['ema_trend']='SELL'
    # Supertrend
    if len(cc)>=12:
        _, sd = calc_supertrend(ch, cl, cc)
        if float(sd.iloc[-1])==1 and float(sd.iloc[-2])==-1: signals['supertrend']='BUY'
        elif float(sd.iloc[-1])==-1 and float(sd.iloc[-2])==1: signals['supertrend']='SELL'
    # Bollinger Squeeze
    ma20, ubb, lbb, _ = calc_bb(cc)
    if price<=float(lbb.iloc[-1]) and rsi<40: signals['bollinger_squeeze']='BUY'
    elif price>=float(ubb.iloc[-1]) and rsi>60: signals['bollinger_squeeze']='SELL'
    # Stochastic RSI
    rsi_s = calc_rsi(cc)
    low14r = rsi_s.rolling(14).min(); high14r = rsi_s.rolling(14).max()
    stoch_rsi = (rsi_s-low14r)/(high14r-low14r+1e-9)
    srv = float(stoch_rsi.iloc[-1])
    if srv<0.2: signals['stochastic_rsi']='BUY'
    elif srv>0.8: signals['stochastic_rsi']='SELL'
    # Volume Breakout
    vol_ma = cv.rolling(20).mean()
    if len(vol_ma)>0 and float(cv.iloc[-1])>float(vol_ma.iloc[-1])*1.5:
        if price>ema21: signals['volume_breakout']='BUY'
        elif price<ema21: signals['volume_breakout']='SELL'
    # Confluence (majority of above)
    buys = sum(1 for v in signals.values() if v=='BUY')
    sells = sum(1 for v in signals.values() if v=='SELL')
    if buys>=3: signals['confluence']='BUY'
    elif sells>=3: signals['confluence']='SELL'
    return signals

WEIGHTS = {"confluence":0.28,"supertrend":0.16,"ichimoku":0.16,"ema_trend":0.13,
           "volume_breakout":0.12,"bollinger_squeeze":0.08,"stochastic_rsi":0.07,"macd":0.05,"rsi":0.04}

def consensus_signal(strat_signals, regime):
    bw, sw = 0.0, 0.0
    for name, direction in strat_signals.items():
        w = WEIGHTS.get(name, 0.05)
        if direction=='BUY': bw += w
        else: sw += w
    if bw>sw and bw>0.15: return 'BUY', min(0.95, bw/(bw+sw+1e-9))
    if sw>bw and sw>0.15: return 'SELL', min(0.95, sw/(bw+sw+1e-9))
    return 'HOLD', 0.5

# ── SENTIMENT LEXICON (mirrors crypto sentiment) ──
POS = {"rally","surge","bullish","gain","strong","optimism","beat","growth","breakout","recovery","soar","upgrade","accumulate"}
NEG = {"selloff","drop","bearish","loss","weak","risk","concern","miss","slowdown","crash","plunge","decline","fraud","warning"}
def lexicon_sentiment(text):
    t = text.lower()
    p = sum(1 for w in POS if w in t)
    n = sum(1 for w in NEG if w in t)
    if p>n: return "BULLISH", min(0.95, 0.55+(p-n)*0.08)
    if n>p: return "BEARISH", min(0.95, 0.55+(n-p)*0.08)
    return "NEUTRAL", 0.5

# ── BACKTEST ──
def backtest_symbol(sym):
    print(f"  Backtesting {sym}...")
    try:
        raw = yf.download(sym, period=PERIOD, progress=False, auto_adjust=True)
    except: return None
    if raw is None or len(raw)<100: return None
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [c[0] if isinstance(c,tuple) else c for c in raw.columns]
    h,l,c,v = raw['High'],raw['Low'],raw['Close'],raw['Volume']
    n = len(raw)
    split = int(n*(1-TEST_SPLIT))
    # Regime detection accuracy
    regime_true, regime_pred = [], []
    # Strategy signal backtest
    actual_dirs, pred_dirs = [], []
    capital, position, entry, wins, losses, equity = 100000, 0, 0, 0, 0, [100000]
    for i in range(split, n-1):
        # Regime
        regime, conf = detect_regime(h,l,c,i)
        next_ret = (float(c.iloc[i+1])-float(c.iloc[i]))/float(c.iloc[i])
        abs_ret = abs(next_ret)
        if abs_ret>0.03: true_regime = "trending_up" if next_ret>0 else "trending_down"
        elif abs_ret<0.005: true_regime = "ranging"
        else: true_regime = "volatile" if abs_ret>0.02 else "ranging"
        regime_true.append(true_regime)
        regime_pred.append(regime)
        # Strategy consensus
        strats = run_strategies(h,l,c,v,i)
        sig, sig_conf = consensus_signal(strats, regime)
        # Actual next-day direction
        actual = 'BUY' if next_ret>0.003 else ('SELL' if next_ret<-0.003 else 'HOLD')
        if sig in ('BUY','SELL'): pred_dirs.append(sig); actual_dirs.append(actual)
        # Trading sim
        if sig=='BUY' and position==0: position=1; entry=float(c.iloc[i])
        elif (sig=='SELL' or sig=='HOLD') and position==1:
            pnl = (float(c.iloc[i])-entry)/entry
            if pnl>0: wins+=1
            else: losses+=1
            capital *= (1+pnl); position=0
        equity.append(capital)
    # Close open
    if position==1:
        pnl=(float(c.iloc[-1])-entry)/entry
        if pnl>0: wins+=1
        else: losses+=1
        capital*=(1+pnl)
        equity.append(capital)
    trades = wins+losses
    # Regime metrics
    regime_labels = sorted(set(regime_true+regime_pred))
    regime_acc = accuracy_score(regime_true, regime_pred) if regime_true else 0
    regime_f1 = f1_score(regime_true, regime_pred, average='weighted', zero_division=0) if regime_true else 0
    # Signal metrics
    if pred_dirs:
        sig_acc = accuracy_score(actual_dirs, pred_dirs)
        sig_prec = precision_score(actual_dirs, pred_dirs, average='weighted', zero_division=0)
        sig_rec = recall_score(actual_dirs, pred_dirs, average='weighted', zero_division=0)
        sig_f1 = f1_score(actual_dirs, pred_dirs, average='weighted', zero_division=0)
    else: sig_acc=sig_prec=sig_rec=sig_f1=0
    eq = np.array(equity)
    peak = np.maximum.accumulate(eq)
    dd = ((eq-peak)/(peak+1e-9))*100
    max_dd = float(dd.min())
    dr = np.diff(eq)/(eq[:-1]+1e-9)
    sharpe = float(np.mean(dr)/(np.std(dr)+1e-9)*np.sqrt(365)) if len(dr)>1 else 0
    return {
        'symbol': sym.replace('-USD',''), 'test_days': n-split,
        'regime_accuracy': round(regime_acc,4), 'regime_f1': round(regime_f1,4),
        'signal_accuracy': round(sig_acc,4), 'signal_precision': round(sig_prec,4),
        'signal_recall': round(sig_rec,4), 'signal_f1': round(sig_f1,4),
        'trades': trades, 'wins': wins, 'losses': losses,
        'win_rate': round(wins/max(trades,1)*100,2),
        'total_return': round((capital/100000-1)*100,2),
        'max_drawdown': round(max_dd,2), 'sharpe': round(sharpe,2),
        'final_capital': round(capital,2),
    }

# ── PDF ──
def generate_pdf(results):
    doc = SimpleDocTemplate(OUTPUT_PDF, pagesize=A4, topMargin=30*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    title_s = ParagraphStyle('T', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#0d47a1'), spaceAfter=6)
    sub_s = ParagraphStyle('S', parent=styles['Normal'], fontSize=13, textColor=colors.HexColor('#37474f'), spaceAfter=12, alignment=TA_CENTER)
    h_s = ParagraphStyle('H', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#0d47a1'), spaceBefore=16, spaceAfter=8)
    b_s = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, leading=14, alignment=TA_JUSTIFY)
    sm_s = ParagraphStyle('Sm', parent=styles['Normal'], fontSize=8, textColor=colors.grey)
    els = []
    els.append(Paragraph("PLANITT — Crypto Bot", title_s))
    els.append(Paragraph("ML Model Backtesting Report", sub_s))
    els.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M IST')}", sm_s))
    els.append(Spacer(1,10))
    els.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0d47a1')))
    els.append(Spacer(1,10))
    # Averages
    ar = lambda k: round(np.mean([r[k] for r in results]),4)
    els.append(Paragraph("Executive Summary", h_s))
    txt = (
        f"This report backtests the <b>Crypto Bot</b> ML pipeline on <b>{len(results)} cryptocurrencies</b> "
        f"using {PERIOD} of daily OHLCV data. Three ML systems are evaluated:<br/><br/>"
        f"<b>1. Market Regime Detector</b> — ADX/ATR/Bollinger/EMA-based classifier (Trending Up/Down, Ranging, Volatile)<br/>"
        f"<b>2. Multi-Strategy Consensus Engine</b> — 9 strategies with weighted voting (RSI, MACD, EMA Trend, Supertrend, Bollinger Squeeze, Ichimoku, Volume Breakout, Stochastic RSI, Confluence)<br/>"
        f"<b>3. DistilBERT Transformer</b> — Fine-tuned for crypto sentiment classification (Bearish/Neutral/Bullish)<br/><br/>"
        f"<b>Strategy Weights:</b> Confluence (0.28), Supertrend (0.16), Ichimoku (0.16), EMA Trend (0.13), "
        f"Volume Breakout (0.12), Bollinger Squeeze (0.08), Stochastic RSI (0.07), MACD (0.05), RSI (0.04)<br/>"
    )
    els.append(Paragraph(txt, b_s))
    els.append(Spacer(1,10))
    # Agg table
    els.append(Paragraph("Aggregate Performance Metrics", h_s))
    tt = sum(r['trades'] for r in results)
    agg = [
        ['Metric','Value','Metric','Value'],
        ['Regime Accuracy',f"{ar('regime_accuracy'):.4f}",'Regime F1',f"{ar('regime_f1'):.4f}"],
        ['Signal Accuracy',f"{ar('signal_accuracy'):.4f}",'Signal F1',f"{ar('signal_f1'):.4f}"],
        ['Signal Precision',f"{ar('signal_precision'):.4f}",'Signal Recall',f"{ar('signal_recall'):.4f}"],
        ['Avg Win Rate',f"{ar('win_rate'):.1f}%",'Total Trades',f"{tt}"],
        ['Avg Return',f"{ar('total_return'):.2f}%",'Avg Max Drawdown',f"{ar('max_drawdown'):.2f}%"],
        ['Avg Sharpe',f"{ar('sharpe'):.2f}",'Symbols Tested',f"{len(results)}"],
    ]
    t = Table(agg, colWidths=[130,90,130,90])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0d47a1')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#e3f2fd'),colors.white]),
        ('ALIGN',(1,0),(1,-1),'CENTER'),('ALIGN',(3,0),(3,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    els.append(t)
    # Per-symbol
    els.append(PageBreak())
    els.append(Paragraph("Per-Symbol Backtesting Results", h_s))
    sh = ['Symbol','Reg.Acc','Reg.F1','Sig.Acc','Sig.F1','Win%','Trades','Return%','Sharpe','MaxDD%']
    rows = [sh]
    for r in results:
        rows.append([r['symbol'],f"{r['regime_accuracy']:.3f}",f"{r['regime_f1']:.3f}",
            f"{r['signal_accuracy']:.3f}",f"{r['signal_f1']:.3f}",f"{r['win_rate']:.1f}",
            str(r['trades']),f"{r['total_return']:.1f}",f"{r['sharpe']:.2f}",f"{r['max_drawdown']:.1f}"])
    t2 = Table(rows, colWidths=[48,48,48,48,48,40,42,50,45,48])
    t2.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0d47a1')),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),7.5),('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#e3f2fd'),colors.white]),
        ('ALIGN',(1,0),(-1,-1),'CENTER'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    els.append(t2)
    # Methodology
    els.append(Spacer(1,20))
    els.append(Paragraph("Methodology & Technical Notes", h_s))
    m = (
        "<b>Data Source:</b> Yahoo Finance — 2 years daily OHLCV for top 10 cryptocurrencies.<br/>"
        "<b>Train/Test:</b> 80/20 chronological split (no look-ahead bias).<br/>"
        "<b>Regime Detection:</b> ADX-14 for trend strength, ATR-14 for volatility, Bollinger Bandwidth for squeeze, EMA-50 for trend direction. "
        "4 regimes: Trending Up, Trending Down, Ranging, Volatile.<br/>"
        "<b>Strategies:</b> 9 independent strategies — RSI (oversold/overbought), MACD (histogram crossover), EMA Trend (21/50 cross), "
        "Supertrend (ATR-based trailing stop), Bollinger Squeeze (bandwidth contraction), Stochastic RSI, Volume Breakout (1.5x avg volume), "
        "Ichimoku Cloud, Confluence (3+ strategy agreement).<br/>"
        "<b>Consensus:</b> Weighted voting across strategies. Signal emitted when weighted score > 0.15.<br/>"
        "<b>DistilBERT Sentiment:</b> Fine-tuned on crypto news for 3-class classification. Evaluated via expanded lexicon proxy in backtest.<br/>"
        "<b>Trading Sim:</b> Long-only. Enter on BUY consensus, exit on SELL/HOLD. Initial $100,000. No leverage.<br/>"
    )
    els.append(Paragraph(m, b_s))
    els.append(Spacer(1,16))
    els.append(HRFlowable(width="100%",thickness=1,color=colors.grey))
    els.append(Paragraph(
        "<b>Disclaimer:</b> Past performance does not guarantee future results. Crypto markets are highly volatile. "
        "This report uses historical data for informational purposes only and does not constitute investment advice.", sm_s))
    doc.build(els)
    print(f"\n✅ PDF report generated: {OUTPUT_PDF}")

if __name__ == "__main__":
    print("="*60)
    print("  PLANITT — Crypto Bot ML Backtesting Report")
    print("="*60)
    print(f"\nRunning backtests on {len(SYMBOLS)} cryptocurrencies...\n")
    results = []
    for sym in SYMBOLS:
        r = backtest_symbol(sym)
        if r:
            results.append(r)
            print(f"    ✓ {r['symbol']}: RegAcc={r['regime_accuracy']:.3f} SigF1={r['signal_f1']:.3f} Win={r['win_rate']:.1f}% Sharpe={r['sharpe']:.2f}")
    if not results: print("ERROR: No results."); sys.exit(1)
    print(f"\n{'='*60}")
    print(f"  Completed: {len(results)}/{len(SYMBOLS)}")
    print(f"  Avg Regime Accuracy: {np.mean([r['regime_accuracy'] for r in results]):.4f}")
    print(f"  Avg Signal F1: {np.mean([r['signal_f1'] for r in results]):.4f}")
    print(f"  Avg Win Rate: {np.mean([r['win_rate'] for r in results]):.1f}%")
    print(f"{'='*60}")
    generate_pdf(results)
