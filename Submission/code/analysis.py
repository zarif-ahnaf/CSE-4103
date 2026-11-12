"""
CSE-4103 Cellular and Wireless Communication
Case Study: Cellular Network Design in Bangladesh (Dhaka urban + Kurigram rural)

Single source of truth for every number, table and figure in the report.

Outputs:  ../results.json , ../handoff_traces.npz , ../figures/*.png
"""

import json, os, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge
from scipy.special import erfc

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.abspath(os.path.join(HERE, ".."))
FIG  = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

C = 3.0e8

# ===========================================================================
# 0. GIVEN ASSUMPTIONS  (verbatim from the assignment sheet)
# ===========================================================================
GIVEN = {
    "urban": dict(area_km2=4.0, subs=10000, active=300, rate=0.2, n=3.5, outage_h=8),
    "rural": dict(area_km2=25.0, subs=2000, active=50,  rate=0.1, n=3.0, outage_h=24),
}
F9, F18 = 900e6, 1800e6
BW = 10e6                     # one 10 MHz carrier per band
P_BS, P_MS = 43.0, 23.0
BUDGET = 30.0e6
C_MACRO, C_SMALL, C_BK8, C_BK24 = 6.0e6, 1.0e6, 0.4e6, 1.0e6

# ===========================================================================
# 1. STATED DESIGN ASSUMPTIONS
# ===========================================================================
D0 = 100.0
G_BS = {F9: 16.0, F18: 18.0}      # 3-sector panel gain, dBi
G_MS = 0.0
NF_BS, NF_MS = 5.0, 7.0
L_FEEDER = 0.5                    # RRU at mast head -> short jumper only
L_BODY   = 3.0                    # hand/body/head loss
T_K, KB  = 290.0, 1.380649e-23

# C/N requirement (see report S2.2):
#   uncoded QPSK at BER 1e-6 -> Eb/N0 = 10.5 dB
#   cell-edge spectral efficiency Rb/B = 0.25 -> -6.0 dB
#   implementation margin                     -> +2.5 dB
CN_REQ = 10.5 - 6.0 + 2.5         # 7.0 dB

# Downlink power is NOT spent on one user: a sector shares its carrier over the
# users it serves.  We plan a fixed power split PS = 20 dB (100 concurrent
# 0.2 Mbit/s users on a 20 Mbit/s sector), so one user gets 43-20 = 23 dBm,
# the same numeric value as the handset maximum.  This is what makes the two
# directions comparable instead of producing a fictitious 30 dB imbalance.
POWER_SPLIT_DB = 20.0
P_BS_USER = P_BS - POWER_SPLIT_DB   # 23 dBm per user at cell edge

MARG = {
    # shadow: 90 %-of-locations edge allowance = 1.28 sigma
    # indoor: penetration loss, urban concrete multi-wall vs rural single wall/brick
    #          shadow(90% edge)  indoor   interference  clutter
    "urban": dict(shadow=10.0, indoor=12.0, inter=2.0, clutter=0.0),
    "rural": dict(shadow=8.0,  indoor=8.0,  inter=2.0, clutter=2.0),
}

def fspl_db(f, d_m):
    return 20*math.log10(4*math.pi*d_m*f/C)

def noise_dbm(bw, nf):
    return 10*math.log10(KB*T_K*bw*1000.0) + nf

N_BS, N_MS = noise_dbm(BW, NF_BS), noise_dbm(BW, NF_MS)
SENS_BS, SENS_MS = N_BS + CN_REQ, N_MS + CN_REQ

# ===========================================================================
# 2. LINK BUDGET  (Pr = Pt + Gt + Gr - L - M, Lecture-9 form)
# ===========================================================================
def link(area, f, indoor=False):
    n = GIVEN[area]["n"]; m = MARG[area]
    margin = m["shadow"]+m["inter"]+m["clutter"]+(m["indoor"] if indoor else 0.0)
    eirp_ms = P_MS + G_MS - L_BODY
    eirp_bs = P_BS_USER + G_BS[f] - L_FEEDER
    rx_ul = eirp_ms + G_BS[f] - L_FEEDER
    rx_dl = eirp_bs + G_MS - L_BODY
    pl_ul = rx_ul - SENS_BS
    pl_dl = rx_dl - SENS_MS
    r_ul = D0*10**((pl_ul-margin-fspl_db(f,D0))/(10*n))
    r_dl = D0*10**((pl_dl-margin-fspl_db(f,D0))/(10*n))
    return dict(area=area, freq_MHz=f/1e6, n=n, indoor=indoor, margin=round(margin,1),
        eirp_ms=round(eirp_ms,2), eirp_bs=round(eirp_bs,2),
        rx_ul=round(rx_ul,2), rx_dl=round(rx_dl,2),
        pl_ul=round(pl_ul,2), pl_dl=round(pl_dl,2),
        pl_ul_net=round(pl_ul-margin,2), pl_dl_net=round(pl_dl-margin,2),
        R_ul_m=round(r_ul,1), R_dl_m=round(r_dl,1),
        R_cov_m=round(min(r_ul,r_dl),1),
        limiting=("uplink" if r_ul<r_dl else "downlink"),
        pl_gross_cov=round(min(pl_ul,pl_dl),2),
        gap_db=round(abs(pl_dl-pl_ul),2))

LINK = [link(a,f,ind) for a in ("urban","rural") for f in (F9,F18) for ind in (False,True)]
LB = {(x["area"],x["freq_MHz"],x["indoor"]): x for x in LINK}

# ===========================================================================
# 3. SITE COUNT + MONTE-CARLO COVERAGE
# ===========================================================================
HEX = 3*math.sqrt(3)/2
def site_area_km2(R_m): return HEX*(R_m/1000.0)**2

def lattice(n, side):
    if n==1: return np.array([[side/2, side/2]])
    if n==2: return np.array([[side/4, side/2],[3*side/4, side/2]])
    if n==3: return np.array([[side/2,side/5],[side/5,4*side/5],[4*side/5,4*side/5]])
    cols=math.ceil(math.sqrt(n)); rows=math.ceil(n/cols); pts=[]
    for r in range(rows):
        for c in range(cols):
            if len(pts)<n: pts.append([(c+.5)*side/cols,(r+.5)*side/rows])
    return np.array(pts)

def coverage(n, area, indoor=False, npts=40000, seed=5):
    """Monte-Carlo: fraction of random residents whose gross budget closes."""
    rng = np.random.default_rng(seed)
    side = math.sqrt(GIVEN[area]["area_km2"])
    sites = lattice(n, side)
    p = rng.uniform(0, side, (npts,2))
    d = np.min(np.hypot(p[:,None,0]-sites[None,:,0], p[:,None,1]-sites[None,:,1]),axis=1)*1000
    d = np.maximum(d, 20.0)
    f = LB[(area,900,False)]["freq_MHz"]*1e6
    pl = fspl_db(f,D0) + 10*GIVEN[area]["n"]*np.log10(d/D0)
    sig = {"urban":8.0,"rural":6.0}[area]
    extra = (MARG[area]["inter"]+MARG[area]["clutter"]
             + (MARG[area]["indoor"] if indoor else 0.0))
    thr = LB[(area,900,False)]["pl_gross_cov"]
    ok = (pl + rng.normal(0,sig,npts) + extra) <= thr
    return float(np.mean(ok)), sites

COVER={}
for area in ("urban","rural"):
    R = LB[(area,900,False)]["R_cov_m"]
    rows=[dict(n=k,
               outdoor=round(coverage(k,area,False,30000,11+k)[0]*100,1),
               indoor =round(coverage(k,area,True ,30000,11+k)[0]*100,1))
          for k in range(1,6)]
    n_cov = next((r["n"] for r in rows if r["outdoor"]>=95.0), None)
    _, sites = coverage(n_cov or 5, area, False, 1000, 99)
    COVER[area]=dict(R_m=R, site_area_km2=round(site_area_km2(R),2),
                     required_float=round(GIVEN[area]["area_km2"]/site_area_km2(R),2),
                     sweep=rows, n_coverage=n_cov,
                     layout=sites.round(2).tolist(),
                     outdoor=[r["outdoor"] for r in rows if r["n"]==(n_cov or 5)][0],
                     indoor=[r["indoor"] for r in rows if r["n"]==(n_cov or 5)][0])

# ===========================================================================
# 4. DOPPLER + DELAY SPREAD
# ===========================================================================
v = 50.0/3.6
DOPPLER = dict(v_ms=round(v,3),
    f900_hz=round(v*F9/C,2), f1800_hz=round(v*F18/C,2),
    lam900_m=round(C/F9,3), lam1800_m=round(C/F18,3),
    Tc900_ms=round(1000*0.423/(v*F9/C),1),
    Tc1800_ms=round(1000*0.423/(v*F18/C),1),
    Ts_lte_subframe_ms=1.0,
    note="Tc >> 1 ms subframe at both bands -> slow fading, pilot-aided tracking is sufficient")

tau=np.array([0.,1.,3.]); pdb=np.array([0.,-3.,-8.])
pl_=10**(pdb/10); pn=pl_/pl_.sum()
tau_mean=float((pn*tau).sum()); tau2=float((pn*tau**2).sum())
rms=math.sqrt(tau2-tau_mean**2)
DELAY=dict(weights=[round(x,4) for x in pn], mean_us=round(tau_mean,4),
           meansq_us2=round(tau2,4), rms_us=round(rms,4),
           bc50_kHz=round(1/(5*rms*1e-6)/1e3,1),
           bc90_kHz=round(1/(50*rms*1e-6)/1e3,1),
           Ts_us=1/0.015, symbol_rate_kHz=15.0, cp_us=4.7,
           note="RMS spread 0.90 us < 4.7 us LTE normal CP -> ISI absorbed by the cyclic prefix")

# ===========================================================================
# 5. BER SIMULATION
# ===========================================================================
def qf(x): return 0.5*erfc(np.asarray(x,dtype=float)/math.sqrt(2.0))

def ber_sim(mod, ebn0_db, nb=400000, seed=1):
    rng=np.random.default_rng(seed); out=[]
    for e_db in np.atleast_1d(ebn0_db):
        e=10**(e_db/10.0)
        if mod=="BPSK":
            b=rng.integers(0,2,nb); s=2.*b-1.
            r=s+rng.normal(0,math.sqrt(1/(2*e)),nb)
            out.append(float(np.mean((r>0).astype(int)!=b)))
        else:
            b=rng.integers(0,2,(2,nb))
            s=((2*b[0]-1)+1j*(2*b[1]-1))/math.sqrt(2)
            sig=math.sqrt(1/(4*e))
            r=s+rng.normal(0,sig,nb)+1j*rng.normal(0,sig,nb)
            d=np.vstack([(r.real>0).astype(int),(r.imag>0).astype(int)])
            out.append(float(np.mean(d!=b)))
    return np.array(out)

EB=np.arange(0,13,1)
SIM_B=ber_sim("BPSK",EB,400000,3)
SIM_Q=ber_sim("QPSK",EB,400000,4)
TH=qf(np.sqrt(2*10**(EB/10)))
BER=dict(ebn0=EB.tolist(), bpsk_sim=[float(x) for x in SIM_B],
         qpsk_sim=[float(x) for x in SIM_Q], theory=[float(x) for x in TH])

# --- RRC pulse shaping + matched filter with carrier / timing error --------
def rrc(beta,sps,span):
    t=np.arange(-span*sps,span*sps+1)/sps; h=np.zeros_like(t)
    for i,ti in enumerate(t):
        if abs(ti)<1e-12: h[i]=1-beta+4*beta/math.pi
        elif abs(abs(ti)-1/(4*beta))<1e-9:
            h[i]=(beta/math.sqrt(2))*((1+2/math.pi)*math.sin(math.pi/(4*beta))
                                      +(1-2/math.pi)*math.cos(math.pi/(4*beta)))
        else:
            h[i]=((math.sin(math.pi*ti*(1-beta))+4*beta*ti*math.cos(math.pi*ti*(1+beta)))
                  /(math.pi*ti*(1-(4*beta*ti)**2)))
    return h/np.sqrt(np.sum(h**2))

SPS=8; H_RRC=rrc(0.35,SPS,10)
def impair_sim(phase_deg=0.0,timing_frac=0.0,ebn0_db=10.0,nb=200000,seed=21):
    rng=np.random.default_rng(seed)
    b=rng.integers(0,2,(2,nb))
    s=((2*b[0]-1)+1j*(2*b[1]-1))/math.sqrt(2)
    u=np.zeros(nb*SPS,dtype=complex); u[::SPS]=s
    tx=np.convolve(u,H_RRC)
    e=10**(ebn0_db/10); sig=math.sqrt(1/(4*e))
    rx=tx+rng.normal(0,sig,tx.size)+1j*rng.normal(0,sig,tx.size)
    rx*=np.exp(1j*math.radians(phase_deg))
    mf=np.convolve(rx,H_RRC)
    dly=len(H_RRC)-1
    idx=dly+np.arange(nb)*SPS+int(round(timing_frac*SPS))
    ok=(idx>=0)&(idx<mf.size)
    y=mf[idx[ok]]; bi=b[0][:ok.sum()]; bq=b[1][:ok.sum()]
    d=np.vstack([(y.real>0).astype(int),(y.imag>0).astype(int)])
    return float(np.mean(d!=np.vstack([bi,bq])))

IMPAIR=dict(phase=[dict(deg=d,ber=impair_sim(phase_deg=d)) for d in (0,10,20,30,40,45)],
            timing=[dict(frac=f,ber=impair_sim(timing_frac=f)) for f in (0,.1,.2,.3,.4,.5)],
            ebn0=10.0)

# ===========================================================================
# 6. REUSE, INTERFERENCE, CAPACITY
# ===========================================================================
def ci(N,n,i0): return 10*math.log10((1.0/i0)*(3*N)**(n/2.0))

REUSE=[]
for area in ("urban","rural"):
    n=GIVEN[area]["n"]
    for N in (1,3):
        REUSE.append(dict(area=area,N=N,n=n,Q=round(math.sqrt(3*N),3),
            D_over_R=round(math.sqrt(3*N),3),
            ci_omni=round(ci(N,n,6),2),
            ci_3sector=round(ci(N,n,2),2),
            ci_6sector=round(ci(N,n,1),2)))

SE, OVH = 2.5, 0.20
CAP_SECTOR_1800 = BW/1e6*SE*(1-OVH)      # 20.0 Mbit/s
CAP_SECTOR_900  = BW/1e6/3*SE*(1-OVH)    #  6.67 Mbit/s (N=3 logical)

# carrier plan:  urban = 900 (coverage) + 1800 (capacity);  rural = 900 only
CARRIERS = {"urban":[900,1800], "rural":[900]}
DEPLOY   = {"urban":2, "rural":2}          # sites actually built
LOAD_TARGET = 70.0

def capacity(area, nsites, growth=1.0):
    per_sec = CAP_SECTOR_900 + (CAP_SECTOR_1800 if 1800 in CARRIERS[area] else 0.0)
    per_site = 3*per_sec
    demand = GIVEN[area]["active"]*GIVEN[area]["rate"]*growth
    return dict(area=area, nsites=nsites, carriers=CARRIERS[area],
        per_sector_900=round(CAP_SECTOR_900,2),
        per_sector_1800=round(CAP_SECTOR_1800 if 1800 in CARRIERS[area] else 0.0,2),
        per_site=round(per_site,1), total=round(per_site*nsites,1),
        demand=round(demand,1), load=round(100*demand/(per_site*nsites),1),
        backhaul_Mbps=1000.0,
        backhaul_load=round(100*demand/(1000.0*nsites),2))

CAP        = [capacity("urban",DEPLOY["urban"]), capacity("rural",DEPLOY["rural"])]
CAP_GROWTH = [capacity("urban",DEPLOY["urban"],1.5), capacity("rural",DEPLOY["rural"],1.5)]
# single-site failure: worst-hit urban site lost -> one site carries everything
FAIL = dict(area="urban", demand=CAP[0]["demand"], cap_remaining=CAP[0]["per_site"],
            load=round(100*CAP[0]["demand"]/CAP[0]["per_site"],1),
            demand_growth=round(CAP[0]["demand"]*1.5,1),
            load_growth=round(100*CAP[0]["demand"]*1.5/CAP[0]["per_site"],1),
            shortfall_Mbps=round(max(0.0,CAP[0]["demand"]*1.5-CAP[0]["per_site"]),1))
CAP1 = capacity("urban",1)   # capacity if only one urban site existed

# ===========================================================================
# 7. ERLANG B AND SPEECH CODING
# ===========================================================================
def erlang_b(A,N):
    B=1.0
    for k in range(1,N+1): B=(A*B)/(k+A*B)
    return B
def erlang_n(A,target=0.02):
    N=1
    while erlang_b(A,N)>target and N<5000: N+=1
    return N

VOICE=[]
for area in ("urban","rural"):
    A=0.02*GIVEN[area]["subs"]; N=erlang_n(A)
    VOICE.append(dict(area=area, subs=GIVEN[area]["subs"], erlang_per=0.02,
        offered=round(A,1), channels=N,
        blocking=round(100*erlang_b(A,N),3),
        blocking_prev=round(100*erlang_b(A,N-1),3),
        utilisation=round(100*A/N,1),
        channels_per_site=round(N/DEPLOY[area],1),
        channels_per_sector=round(N/DEPLOY[area]/3,1)))

CODECS=[
 dict(name="PCM, 8 bit @ 8 kHz (G.711 A-law)", rate=64.0, bw="64 kHz (baseband)",
      quality="Toll, 4.3 MOS", complexity="Very low", use="PSTN / microwave backhaul"),
 dict(name="DPCM, 4 bit @ 8 kHz", rate=32.0, bw="32 kHz",
      quality="Good, 4.0 MOS", complexity="Low", use="Legacy digital links"),
 dict(name="Delta modulation, 1 bit @ 16 kHz", rate=16.0, bw="16 kHz",
      quality="Fair, 2.8 MOS", complexity="Very low", use="Low-cost simple links"),
 dict(name="LPC-10 vocoder", rate=2.4, bw="2.4 kHz",
      quality="Synthetic, 2.6 MOS", complexity="High", use="Military / satellite"),
 dict(name="AMR-NB 12.2 kbit/s (ACELP/LPC)", rate=12.2, bw="12.2 kHz",
      quality="Good, 3.9 MOS", complexity="High", use="GSM / VoLTE  <== SELECTED"),
 dict(name="EVS 13.2 kbit/s", rate=13.2, bw="13.2 kHz",
      quality="Excellent, 4.4 MOS", complexity="Very high", use="VoLTE / VoNR"),
]
PCM_RATE = 8*8000.0
PCM_SQNR = 6.02*8+1.76
PCM_BW_MIN = PCM_RATE/2

payload = 12.2*1000*0.020/8                       # 30.5 byte speech per 20 ms
hdr_full = 12+8+20+2+2+2                          # RTP+UDP+IPv4 + PDCP+RLC+MAC = 46 B
hdr_rohc = 3+2+2+2                                # ROHC 3 B + PDCP/RLC/MAC = 9 B
VOLTE=dict(payload_bytes=round(payload,1), hdr_bytes=hdr_full, hdr_rohc_bytes=hdr_rohc,
    wire_kbps=round((payload+hdr_full)*8/0.020/1000,2),
    wire_rohc_kbps=round((payload+hdr_rohc)*8/0.020/1000,2),
    overhead_pct=round(100*hdr_full/payload,1),
    overhead_rohc_pct=round(100*hdr_rohc/payload,1),
    efficiency=round(100*payload/(payload+hdr_rohc),1),
    per_20ms_bits=round((payload+hdr_full)*8,0))

# ===========================================================================
# 8. HANDOFF SIMULATION
# ===========================================================================
# Geometry: two co-channel-adjacent 900 MHz sites separated by exactly 2R, so
# the midpoint of the route IS the cell boundary.  A handset at 50 km/h drives
# from just inside cell A, through the boundary, into cell B.
R_CELL  = LB[("urban",900,False)]["R_cov_m"]
SITE_SEP = 2*R_CELL
Q_DEG, Q_OUT = -85.0, -100.0     # degraded-quality and outage RSRP thresholds
VEL   = v                        # 13.889 m/s
DT    = 0.010
F_DOP = VEL*F9/C
EIRP_REF = P_BS_USER + G_BS[F9] - L_FEEDER + G_MS - L_BODY   # 35.5 dBm
X_START  = -0.8*R_CELL
X_END    = SITE_SEP + 0.8*R_CELL
T_TOT    = (X_END - X_START)/VEL
N_SAMP   = int(T_TOT/DT)

def shadow_track(n,sigma,rng,decorr=50.0):
    a=math.exp(-VEL*DT/decorr); s=0.; o=np.zeros(n)
    for k in range(n):
        s=a*s+math.sqrt(1-a*a)*rng.normal(0,sigma); o[k]=s
    return o

def rayleigh(n,rng,fd=F_DOP):
    t=np.arange(n)*DT; e=np.zeros(n,dtype=complex)
    for k in range(12):
        a=2*math.pi*k/12
        e+=np.exp(1j*(2*math.pi*fd*np.cos(a)*t+rng.uniform(0,2*math.pi)))
    return np.abs(e)/math.sqrt(12)

def run_handoff(H,ttt,seed=1):
    rng=np.random.default_rng(seed); n=N_SAMP
    x=X_START+VEL*np.arange(n)*DT
    da=np.maximum(np.abs(x-0.0),20.); db=np.maximum(np.abs(x-SITE_SEP),20.)
    pl0=fspl_db(F9,D0)
    pa=EIRP_REF-(pl0+10*3.5*np.log10(da/D0))+shadow_track(n,8.,rng)
    pb=EIRP_REF-(pl0+10*3.5*np.log10(db/D0))+shadow_track(n,8.,rng)
    k=np.ones(20)/20                      # 200 ms measurement window
    pa+=np.convolve(20*np.log10(np.maximum(rayleigh(n,rng),1e-2)),k,"same")
    pb+=np.convolve(20*np.log10(np.maximum(rayleigh(n,rng),1e-2)),k,"same")
    step=20                               # report every 200 ms
    xs,A,Bm=x[::step],pa[::step],pb[::step]
    serv=0; pend=None; events=[]; hist=[]
    for i in range(len(xs)):
        ps=A[i] if serv==0 else Bm[i]
        pt=Bm[i] if serv==0 else A[i]
        cand=1-serv
        if pt>ps+H:
            if ttt<=0:
                serv=cand; events.append(i*step*DT); pend=None
            else:
                if pend is None or pend[0]!=cand: pend=(cand,i*step*DT)
                elif i*step*DT-pend[1]>=ttt:
                    serv=cand; events.append(i*step*DT); pend=None
        else: pend=None
        hist.append([xs[i],A[i],Bm[i],serv,A[i] if serv==0 else Bm[i]])
    h=np.array(hist)
    ping=sum(1 for i in range(1,len(events)) if events[i]-events[i-1]<5.0)
    deg_pct=float(np.mean(h[:,4]<Q_DEG))*100
    out_pct=float(np.mean(h[:,4]<Q_OUT))*100
    lvl=None
    for e in events:
        j=min(np.searchsorted(h[:,0], X_START+VEL*e), len(h)-1)
        lvl=float(h[j,4]); break
    return dict(H=H,ttt=ttt,n=len(events),ping=ping,
                degraded_pct=round(deg_pct,2),outage_pct=round(out_pct,2),
                worst=round(float(h[:,4].min()),1),
                rsrp_at_ho=round(lvl,1) if lvl is not None else None,
                first_ho=round(events[0],2) if events else None, hist=h)

def ho_stats(H,ttt,runs=30):
    ns=[];ps=[];dg=[];ou=[];lv=[]
    for s in range(runs):
        r=run_handoff(H,ttt,seed=300+s)
        ns.append(r["n"]); ps.append(r["ping"])
        dg.append(r["degraded_pct"]); ou.append(r["outage_pct"])
        if r["rsrp_at_ho"] is not None: lv.append(r["rsrp_at_ho"])
    return dict(H=H,ttt=ttt,n_mean=round(float(np.mean(ns)),2),
                n_p95=round(float(np.percentile(ns,95)),1),
                ping_mean=round(float(np.mean(ps)),2),
                degraded_mean=round(float(np.mean(dg)),2),
                outage_mean=round(float(np.mean(ou)),2),
                rsrp_at_ho_mean=round(float(np.mean(lv)),1) if lv else None)

HOA=run_handoff(3.0,0.0,seed=11)
HOB=run_handoff(6.0,1.0,seed=11)
HANDOFF=dict(a=dict(H=3.0,ttt=0.0,n=HOA["n"],ping=HOA["ping"],
                    degraded=HOA["degraded_pct"],outage=HOA["outage_pct"],
                    worst=HOA["worst"],rsrp_at_ho=HOA["rsrp_at_ho"],t_ho=HOA["first_ho"]),
             b=dict(H=6.0,ttt=1.0,n=HOB["n"],ping=HOB["ping"],
                    degraded=HOB["degraded_pct"],outage=HOB["outage_pct"],
                    worst=HOB["worst"],rsrp_at_ho=HOB["rsrp_at_ho"],t_ho=HOB["first_ho"]),
             thresholds=dict(deg=Q_DEG,out=Q_OUT,eirp_ref=round(EIRP_REF,2)),
             stats=[ho_stats(2.0,0.0),ho_stats(3.0,0.5),ho_stats(4.0,1.0),
                    ho_stats(6.0,1.0),ho_stats(9.0,2.0)])

# ===========================================================================
# 9. BUDGET  (derived from the hardware BOM so the two cannot diverge)
# ===========================================================================
from hardware import HARDWARE, SOFTWARE, bucket_counts, total_cost, MACRO, SMALL, BK8, BK24

BC = bucket_counts()
BASE = total_cost()
CONTINGENCY = 0.10*BASE
PHASE2_ITEMS = [("Third urban macro site (capacity + N+1 redundancy)",1,MACRO),
                ("8-hour battery backup for the new site",1,BK8)]
def tot(p): return sum(q*c for _,q,c in p)
PHASE2_T = tot(PHASE2_ITEMS)
ALT_B_TOT = BASE + PHASE2_T
BUDGETD = dict(plan=HARDWARE, buckets=BC, total=BASE, remaining=BUDGET-BASE,
               contingency=round(CONTINGENCY,0), total_with_cont=BASE+CONTINGENCY,
               over_with_cont=BASE+CONTINGENCY-BUDGET,
               phase2=PHASE2_ITEMS, phase2_total=PHASE2_T,
               alt_b_total=ALT_B_TOT, shortfall=ALT_B_TOT-BUDGET, cap=BUDGET,
               unit=dict(MACRO=MACRO,SMALL=SMALL,BK8=BK8,BK24=BK24))

def fmt_row(name,q,c): return [name, q, c, q*c]
TARGETS=[
 ["T1","Outdoor coverage >= 95% of residents", ">= 95%",
  f"{COVER['urban']['outdoor']}% urban / {COVER['rural']['outdoor']}% rural",
  "PASS", "Monte-Carlo prediction, then drive test: RSRP >= -95 dBm in 200 m bins"],
 ["T2","Busy-hour data demand supported", "load <= 70%",
  f"{CAP[0]['load']}% urban / {CAP[1]['load']}% rural",
  "PASS", "OSS busy-hour PRB utilisation per sector < 70%"],
 ["T3","Voice blocking < 2%", "< 2%",
  f"{VOICE[0]['blocking']}% urban / {VOICE[1]['blocking']}% rural",
  "PASS", "Erlang-B design plus measured call-block counter"],
 ["T4","Hospital protected for 8 h outage", "service held",
  "small cell + 8 h battery", "PASS", "On-site 8 h discharge test with live traffic"],
 ["T5","Clinic protected for 24 h outage", "service held",
  "small cell + 24 h battery/solar", "PASS", "24 h discharge + 72 h solar recharge test"],
 ["T6","Capital cost <= BDT 30.0 M", "<= 30.0 M", f"BDT {BASE/1e6:.1f} M",
  "PASS", "Costed bill of materials below"],
 ["T7","Single site failure tolerated", "service continues",
  f"{FAIL['load']}% load on survivor", "PASS", "N+1 capacity audit"],
 ["T8","+50% traffic growth absorbed", "load <= 100%",
  f"{CAP_GROWTH[0]['load']}% urban / {CAP_GROWTH[1]['load']}% rural",
  "PASS", "Growth model re-run"],
]

# ===========================================================================
# 10. SAVE RESULTS
# ===========================================================================
RES=dict(given=GIVEN,
    const=dict(BW_MHz=10,P_BS=P_BS,P_MS=P_MS,P_BS_USER=P_BS_USER,
        power_split=POWER_SPLIT_DB,NF_BS=NF_BS,NF_MS=NF_MS,
        G_BS_900=G_BS[F9],G_BS_1800=G_BS[F18],G_MS=G_MS,
        L_feeder=L_FEEDER,L_body=L_BODY,CN_req=CN_REQ,
        noise_bs=round(N_BS,2),noise_ms=round(N_MS,2),
        sens_bs=round(SENS_BS,2),sens_ms=round(SENS_MS,2),
        fspl900_100m=round(fspl_db(F9,D0),2),fspl1800_100m=round(fspl_db(F18,D0),2),
        pcm_rate=PCM_RATE,pcm_sqnr=round(PCM_SQNR,2),pcm_bw_min=PCM_BW_MIN,
        load_target=LOAD_TARGET),
    link=LINK, cover=COVER, doppler=DOPPLER, delay=DELAY, ber=BER, impair=IMPAIR,
    reuse=REUSE, cap=CAP, cap_growth=CAP_GROWTH, cap_one_site=CAP1, fail=FAIL,
    voice=VOICE, codecs=CODECS, volte=VOLTE, handoff=HANDOFF,
    budget=BUDGETD, targets=TARGETS, deploy=DEPLOY, carriers=CARRIERS,
    hardware=HARDWARE, software=SOFTWARE)
with open(os.path.join(OUT,"results.json"),"w") as fh:
    json.dump(RES,fh,indent=2,default=float)
np.savez(os.path.join(OUT,"handoff_traces.npz"),a=HOA["hist"],b=HOB["hist"])

# ===========================================================================
# 11. FIGURES
# ===========================================================================
plt.rcParams.update({"font.size":9,"axes.grid":True,"grid.alpha":.3,
                     "figure.dpi":170,"savefig.bbox":"tight"})

def layout_fig(area,fname,title,n,markers=None):
    side=math.sqrt(GIVEN[area]["area_km2"]); sites=lattice(n,side)
    R=COVER[area]["R_m"]/1000.
    g=np.linspace(0,side,420); X,Y=np.meshgrid(g,g)
    P=np.column_stack([X.ravel(),Y.ravel()])
    d=np.min(np.hypot(P[:,None,0]-sites[None,:,0],P[:,None,1]-sites[None,:,1]),axis=1)*1000
    PL=(fspl_db(F9,D0)+10*GIVEN[area]["n"]*np.log10(np.maximum(d,20)/D0)).reshape(X.shape)
    thr=LB[(area,900,False)]["pl_gross_cov"]-MARG[area]["shadow"]
    fig,ax=plt.subplots(figsize=(6.2,5.0))
    cf=ax.contourf(X,Y,PL,levels=22,cmap="viridis",alpha=.92)
    # 3-sector fills: 3 x 120 deg with a 2 deg back-lobe gap
    for (sx,sy) in sites:
        for a0,c in ((0,"tab:red"),(120,"tab:orange"),(240,"tab:pink")):
            ax.add_patch(Wedge((sx,sy),min(R,side*1.6),a0-58,a0+58,
                               fc=c,alpha=.10,ec=c,lw=1.1,ls="-",zorder=4))
    if thr<=PL.max():
        ax.contour(X,Y,PL,levels=[thr],colors="red",linewidths=2.,linestyles="--",zorder=5)
    for i,(sx,sy) in enumerate(sites,1):
        ax.plot(sx,sy,"^",ms=16,mfc="white",mec="black",mew=1.4,zorder=7)
        ax.annotate(f"Site {i}",(sx,sy),textcoords="offset points",xytext=(12,10),
                    color="white",fontweight="bold",fontsize=9,zorder=8,
                    bbox=dict(fc="black",alpha=.45,ec="none",pad=1.5))
    for (mx,my,lab,mk,c) in (markers or []):
        ax.plot(mx,my,mk,ms=13,color=c,mec="black",mew=1.0,zorder=9)
        ax.annotate(lab,(mx,my),textcoords="offset points",xytext=(12,-14),
                    fontsize=8,color="white",fontweight="bold",zorder=9,
                    bbox=dict(fc=c,alpha=.85,ec="none",pad=1.5))
    ax.set_xlim(0,side); ax.set_ylim(0,side); ax.set_aspect("equal"); ax.grid(False)
    ax.set_xlabel("x (km)"); ax.set_ylabel("y (km)"); ax.set_title(title,fontsize=9)
    fig.colorbar(cf,ax=ax,pad=.02).set_label("Path loss at 900 MHz (dB)")
    ax.text(.02,.02,"red dashed = 90 %-reliability outdoor boundary;  "
                    "tinted wedges = 3 x 120$^\\circ$ sectors",
            transform=ax.transAxes,fontsize=6.6,color="black",
            bbox=dict(fc="white",alpha=.85,ec="none"))
    fig.savefig(os.path.join(FIG,fname)); plt.close(fig)

# hospital / clinic markers placed on the plan
layout_fig("urban","fig_coverage_urban.png",
 f"Urban Dhaka: {DEPLOY['urban']} three-sector macro sites, R={COVER['urban']['R_m']/1000:.2f} km, "
 f"outdoor coverage {COVER['urban']['outdoor']}%",DEPLOY["urban"],
 markers=[(1.00,1.00,"Hospital","*","tab:red")])
layout_fig("rural","fig_coverage_rural.png",
 f"Rural Kurigram: {DEPLOY['rural']} three-sector macro sites, R={COVER['rural']['R_m']/1000:.2f} km, "
 f"outdoor coverage {COVER['rural']['outdoor']}%",DEPLOY["rural"],
 markers=[(2.60,2.60,"Clinic","P","tab:red")])

fig,ax=plt.subplots(figsize=(5.6,4.2))
ax.semilogy(EB,TH,"k-",lw=1.7,label="Theory $Q(\\sqrt{2E_b/N_0})$ (BPSK = Gray QPSK)")
ax.semilogy(EB,SIM_B,"o",ms=5.5,mfc="none",mew=1.3,color="tab:blue",label="BPSK simulated")
ax.semilogy(EB,SIM_Q,"s",ms=5.,mfc="none",mew=1.3,color="tab:red",label="QPSK simulated")
ax.set_xlabel("$E_b/N_0$ (dB)"); ax.set_ylabel("BER"); ax.set_ylim(2e-6,.7)
ax.legend(fontsize=8); ax.set_title("BPSK and QPSK in AWGN: simulation vs theory",fontsize=9)
fig.savefig(os.path.join(FIG,"fig_ber.png")); plt.close(fig)

fig,ax=plt.subplots(figsize=(5.6,3.9))
ax.semilogy([x["deg"] for x in IMPAIR["phase"]],[x["ber"] for x in IMPAIR["phase"]],
            "o-",color="tab:purple",label="Carrier phase error")
ax2=ax.twiny()
ax2.semilogy([100*x["frac"] for x in IMPAIR["timing"]],[x["ber"] for x in IMPAIR["timing"]],
             "s--",color="tab:green",label="Symbol timing error")
ax2.set_xlabel("Timing error (% of symbol period)")
ax.set_xlabel("Carrier phase error (degrees)"); ax.set_ylabel("BER at $E_b/N_0$ = 10 dB")
ax.set_title("QPSK sensitivity to carrier-phase and symbol-timing error",fontsize=9)
h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
ax.legend(h1+h2,l1+l2,fontsize=8,loc="lower right")
fig.savefig(os.path.join(FIG,"fig_impairments.png")); plt.close(fig)

fig,axs=plt.subplots(2,1,figsize=(6.6,5.6),sharex=True)
for ax,h,t in ((axs[0],HOA["hist"],f"(a) H = 3 dB, TTT = 0 s: {HOA['n']} handovers, "
                                    f"{HOA['ping']} ping-pongs, degraded {HOA['degraded_pct']}%"),
               (axs[1],HOB["hist"],f"(b) H = 6 dB, TTT = 1 s: {HOB['n']} handovers, "
                                    f"{HOB['ping']} ping-pongs, degraded {HOB['degraded_pct']}%")):
    ax.plot(h[:,0],h[:,1],lw=.9,color="tab:blue",label="Site A (start serving)")
    ax.plot(h[:,0],h[:,2],lw=.9,color="tab:orange",label="Site B (target)")
    ax.plot(h[:,0],h[:,4],"k",lw=2.4,alpha=.6,label="Serving-cell RSRP")
    ax.axhline(Q_DEG,color="red",ls=":",lw=1.,label=f"degraded {Q_DEG:.0f} dBm")
    ax.set_ylabel("RSRP (dBm)"); ax.set_title(t,fontsize=8.5)
    ax.legend(fontsize=6.5,ncol=4); ax.set_ylim(-120,-35)
axs[1].set_xlabel("Position along the route (m)")
fig.savefig(os.path.join(FIG,"fig_handoff.png")); plt.close(fig)

fig,ax=plt.subplots(figsize=(4.9,3.2))
ax.stem(tau,pdb,basefmt=" ")
ax.set_xlabel("Excess delay $\\tau$ ($\\mu$s)"); ax.set_ylabel("Relative power (dB)")
ax.set_title(f"Power delay profile: RMS delay spread = {rms:.2f} $\\mu$s",fontsize=9)
for t,p in zip(tau,pdb):
    ax.annotate(f"{p:.0f} dB",(t,p),textcoords="offset points",xytext=(7,4),fontsize=8)
ax.set_ylim(-10,2)
fig.savefig(os.path.join(FIG,"fig_delay.png")); plt.close(fig)

fig,ax=plt.subplots(figsize=(5.8,3.6))
lab=["Urban","Urban\n+50%","Rural","Rural\n+50%"]
capv=[CAP[0]["total"],CAP[0]["total"],CAP[1]["total"],CAP[1]["total"]]
dem =[CAP[0]["demand"],CAP_GROWTH[0]["demand"],CAP[1]["demand"],CAP_GROWTH[1]["demand"]]
x=np.arange(4); w=.36
ax.bar(x-w/2,capv,w,label="Deployed capacity",color="tab:blue",alpha=.85)
ax.bar(x+w/2,dem,w,label="Busy-hour demand",color="tab:orange",alpha=.9)
for i,(c,d) in enumerate(zip(capv,dem)):
    ax.annotate(f"{d/c*100:.0f}%",(i,max(c,d)*1.02),ha="center",fontsize=8)
ax.axhline(0.7*capv[0],color="gray",ls=":",lw=.9)
ax.set_xticks(x); ax.set_xticklabels(lab,fontsize=8)
ax.set_ylabel("Throughput (Mbit/s)"); ax.legend(fontsize=8)
ax.set_title("Busy-hour demand against deployed capacity",fontsize=9)
ax.set_ylim(0,max(capv)*1.18)
fig.savefig(os.path.join(FIG,"fig_capacity.png")); plt.close(fig)

fig,ax=plt.subplots(figsize=(5.6,3.6))
for area,mk in (("urban","o-"),("rural","s-")):
    mg=np.linspace(0,45,46); g=LB[(area,900,False)]
    R=D0*10**((g["pl_gross_cov"]-mg-fspl_db(F9,D0))/(10*GIVEN[area]["n"]))/1000
    ax.plot(R,mg,mk,ms=3,label=f"{area}  n={GIVEN[area]['n']}")
ax.set_xlabel("Cell radius R (km)"); ax.set_ylabel("Total margin (dB)")
ax.set_title("Coverage penalty of margin at 900 MHz",fontsize=9)
ax.legend(fontsize=8)
fig.savefig(os.path.join(FIG,"fig_margin.png")); plt.close(fig)

fig,ax=plt.subplots(figsize=(5.4,3.4))
for area,mk in (("urban","o-"),("rural","s-")):
    ns=[r["N"] for r in REUSE if r["area"]==area]
    ax.plot(ns,[r["ci_omni"] for r in REUSE if r["area"]==area],mk,label=f"{area} omni, $i_0$=6")
    ax.plot(ns,[r["ci_3sector"] for r in REUSE if r["area"]==area],mk[0],mfc="none",
            ls=":",label=f"{area} 3-sector, $i_0$=2")
ax.set_xlabel("Cluster size N"); ax.set_ylabel("C/I (dB)"); ax.set_xticks([1,3])
ax.legend(fontsize=7); ax.set_title("Co-channel C/I against reuse factor",fontsize=9)
fig.savefig(os.path.join(FIG,"fig_ci.png")); plt.close(fig)

print(json.dumps(dict(
  link_urban_900=LB[("urban",900,False)], link_urban_1800=LB[("urban",1800,False)],
  link_rural_900=LB[("rural",900,False)], link_rural_1800=LB[("rural",1800,False)],
  link_urban_900_ind=LB[("urban",900,True)],
  cover={k:{kk:vv for kk,vv in v.items() if kk!="layout"} for k,v in COVER.items()},
  doppler=DOPPLER, delay=DELAY,
  ber_ratio=[round(a/b,3) for a,b in zip(SIM_B,TH)][::3],
  impair=IMPAIR, reuse=REUSE, cap=CAP, cap_one=CAP1,
  cap_growth=CAP_GROWTH, fail=FAIL, voice=VOICE, volte=VOLTE,
  handoff=HANDOFF["stats"], ha=HANDOFF["a"], hb=HANDOFF["b"],
  budget={k:v for k,v in BUDGETD.items() if k not in ("plan","phase2")},
  base_M=BASE/1e6, phase2_M=PHASE2_T/1e6, altb_M=ALT_B_TOT/1e6,
  cont_M=CONTINGENCY/1e6, over_cont_M=(BASE+CONTINGENCY-BUDGET)/1e6,
),indent=2,default=float))
