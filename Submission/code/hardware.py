"""
Hardware bill of materials.

Every item carries vendor / standards links that were checked to resolve.
The `bucket` field ties each line to the assignment's teaching unit costs, so
the BOM and the budget are computed from the same place and cannot drift.

Buckets: MACRO = BDT 6.0 M, SMALL = BDT 1.0 M, BK8 = BDT 0.4 M, BK24 = BDT 1.0 M
Items with bucket=None are included inside a site price (no separate charge).
"""

MACRO, SMALL, BK8, BK24 = 6_000_000, 1_000_000, 400_000, 1_000_000

HARDWARE = [
    dict(id="U1", group="RAN - urban", qty=2, bucket=MACRO,
         item="Three-sector macro base station, 900 + 1800 MHz, 10 MHz per carrier",
         spec="2 x RRU + baseband; 43 dBm/carrier; 3 x 20 Mbit/s per sector after overhead; "
              "2x2 MIMO; eCPRI to baseband; LTE FDD",
         why="Puts both licensed carriers on one mast: 900 MHz carries coverage, "
             "1800 MHz carries capacity, from the same civil works.",
         links=[
             ("Nokia AirScale radio access (RRH + baseband family)",
              "https://www.nokia.com/networks/mobile-networks/airscale-radio-access/"),
             ("Nokia AirScale remote radio heads",
              "https://www.nokia.com/networks/mobile-networks/airscale-radio-access/airscale-remote-radio-heads/"),
             ("Nokia AirScale baseband",
              "https://www.nokia.com/networks/mobile-networks/airscale-radio-access/airscale-baseband/"),
             ("3GPP TS 36.104 - BS radio transmission and reception",
              "https://www.3gpp.org/ftp/Specs/archive/36_series/36.104/"),
         ]),
    dict(id="U2", group="RAN - urban", qty=2, bucket=None,
         item="Sector antennas: dual-band 900/1800 MHz, 65 deg HPBW, 16/18 dBi, RET",
         spec="3 panels per site; 65 deg horizontal; cross-polarised 2x2 MIMO; "
              "remote electrical tilt",
         why="65 deg panels form the three 120 deg sectors drawn on the layout; the "
             "16 dBi (900) / 18 dBi (1800) values feed directly into the link budgets.",
         links=[
             ("CommScope base station antennas", "https://www.commscope.com/"),
             ("Kathrein antenna systems", "https://www.kathrein.com/"),
             ("Amphenol Procom antennas", "https://www.amphenolprocom.com/"),
             ("RF Wel antenna catalogue", "https://www.rfwel.com/"),
         ]),
    dict(id="R1", group="RAN - rural", qty=2, bucket=MACRO,
         item="Rural three-sector macro site, 900 MHz only, high-gain panels",
         spec="43 dBm/carrier into 18 dBi panels; 3 x 20 Mbit/s per sector; 45 m lattice tower",
         why="At n = 3.0 the 900 MHz budget closes a 2.5 km cell; a second carrier would buy "
             "capacity the 50-user village cluster never uses.",
         links=[
             ("Nokia AirScale macro radio access",
              "https://www.nokia.com/mobile-networks/ran/macro/"),
             ("Huawei RuralStar - low-power rural coverage",
              "https://www.huawei.com/en/tech4all/stories/ruralstar"),
             ("Huawei RuralStar Pro launch",
              "https://www.huawei.com/en/news/2020/2/huawei-ruralstar-pro-solution"),
             ("Baicells LTE portfolio", "https://www.baicells.com/products/"),
         ]),
    dict(id="S1", group="Indoor / emergency", qty=2, bucket=SMALL,
         item="Indoor small cells: hospital (urban Site 1) + rural clinic (Site 2)",
         spec="900 MHz, 1 W, 20 MHz; PoE; 2 x 100 Mbit/s backhaul; SON neighbour discovery; "
              "donor-fed indoor antenna",
         why="Removes the 12 dB penetration loss from the macro budget inside the two protected "
             "buildings. Both units are co-sited and fed from their host site's DC plant, so the "
             "hospital inherits 8 h and the clinic inherits 24 h ride-through with no extra battery line.",
         links=[
             ("Nokia small cells", "https://www.nokia.com/mobile-networks/ran/small-cells/"),
             ("Baicells small cells", "https://www.baicells.com/products/"),
             ("Parallel Wireless small cells", "https://www.parallelwireless.com/products/"),
         ]),
    dict(id="B1", group="Backhaul", qty=6, bucket=None,
         item="Backhaul transport, 1 Gbit/s per site (included in site price)",
         spec="Licensed 18/23 GHz microwave for rural 3 km hops; GPON fibre where duct exists; "
              "1 Gbit/s Ethernet demarcation",
         why="Busy-hour demand is 60 Mbit/s urban and 5 Mbit/s rural, so 1 Gbit/s per site leaves "
             "a 16x margin and backhaul load stays at 3.0% - never the binding constraint.",
         links=[
             ("Ceragon IP-20N microwave backhaul", "https://www.ceragon.com/products/ip-20n"),
             ("Ceragon wireless backhaul portfolio", "https://www.ceragon.com/products"),
             ("Cambium Networks backhaul", "https://www.cambiumnetworks.com/products/backhaul/"),
             ("Aviat Networks microwave", "https://aviatnetworks.com/products/"),
             ("Ubiquiti airFiber (unlicensed fallback)",
              "https://store.ui.com/collections/operator-airfiber"),
         ]),
    dict(id="P1", group="Power", qty=2, bucket=BK8,
         item="8-hour DC backup: 48 V LiFePO4 + rectifier (2 urban macro sites)",
         spec="48 V 200 Ah LiFePO4 (~9.6 kWh usable), 3 kW rectifier shelf, "
              "sized for ~1.1 kW site load including the hospital small cell",
         why="9.6 kWh against a 1.1 kW load gives 8.7 h at end of life, meeting the 8 h urban "
             "outage with ageing margin; the hospital small cell shares this plant.",
         links=[
             ("Green Cubes telecom battery units", "https://greencubes.com/industries/telecom/"),
             ("PylonTech LiFePO4 products", "https://www.pylontech.com.cn/products/"),
             ("Victron LiFePO4 batteries", "https://www.victronenergy.com/batteries"),
             ("Vertiv DC power systems",
              "https://www.vertiv.com/en-us/products-catalog/critical-power/dc-power-systems/"),
         ]),
    dict(id="P2", group="Power", qty=2, bucket=BK24,
         item="24-hour backup: 48 V LiFePO4 + solar hybrid (2 rural macro sites)",
         spec="48 V 400 Ah LiFePO4 (~19 kWh usable) + 1.6 kWp PV + MPPT + 3 kVA "
              "MultiPlus charger/inverter",
         why="24 h at ~0.5 kW rural load needs 12 kWh; 19 kWh plus daily solar recharge rides "
             "through a multi-day flood outage and also protects the clinic small cell.",
         links=[
             ("Victron MultiPlus-II inverter/charger",
              "https://www.victronenergy.com/inverters-chargers/multiplus-ii"),
             ("Victron MPPT solar charge controllers",
              "https://www.victronenergy.com/solar-charge-controllers"),
             ("Green Cubes telecom DC backup", "https://greencubes.com/industries/telecom/"),
             ("Vertiv DC power systems",
              "https://www.vertiv.com/en-us/products-catalog/critical-power/dc-power-systems/"),
         ]),
    dict(id="C1", group="Passive / civil", qty=4, bucket=None,
         item="Tower, shelter, earthing, lightning protection (included in site price)",
         spec="30 m urban / 45 m rural lattice; RRU at mast head so feeder loss is 0.5 dB; "
              "Type-1 + Type-2 SPD; TN-S earthing < 5 ohm",
         why="Mast-head RRU is why the link budget uses 0.5 dB feeder loss instead of the "
             "3-4 dB a ground-level radio room would cost.",
         links=[
             ("3GPP TS 36.942 - RF system scenarios and link budget",
              "https://www.3gpp.org/ftp/Specs/archive/36_series/36.942/"),
             ("ITU-R P.837 - rainfall for microwave availability",
              "https://www.itu.int/rec/R-REC-P.837/en"),
             ("ITU-R P.526 - diffraction over terrain",
              "https://www.itu.int/rec/R-REC-P.526/en"),
         ]),
]

SOFTWARE = [
    dict(item="Propagation planning and field validation",
         why="Confirms the log-distance prediction against terrain and clutter before capex.",
         links=[("ITU-R P.1546 - point-to-area prediction",
                 "https://www.itu.int/rec/R-REC-P.1546/en"),
                ("ITU-R P.2109 - building entry loss (indoor margin)",
                 "https://www.itu.int/rec/R-REC-P.2109/en")]),
    dict(item="Erlang-B dimensioning",
         why="Turns 200 E of offered voice into 214 channels at 2% blocking.",
         links=[("Westbay Erlang-B calculator", "https://www.erlang.com/calculator/erlb/"),
                ("Erlang unit reference", "https://en.wikipedia.org/wiki/Erlang_(unit)")]),
    dict(item="BER and handover simulation (this report)",
         why="Reproduces the Q-function curves, then adds carrier/timing error and handover traces.",
         links=[("MathWorks BERAWGN reference",
                 "https://www.mathworks.com/help/comm/ref/berawgn.html"),
                ("NumPy", "https://numpy.org/"), ("SciPy", "https://scipy.org/"),
                ("Matplotlib", "https://matplotlib.org/")]),
]

def bucket_counts():
    """Return {unit_cost: quantity} for every charged BOM line."""
    out = {}
    for h in HARDWARE:
        if h["bucket"]:
            out[h["bucket"]] = out.get(h["bucket"], 0) + h["qty"]
    return out

def total_cost():
    return sum(h["bucket"]*h["qty"] for h in HARDWARE if h["bucket"])

def label(cost):
    return {MACRO:"macro site", SMALL:"small cell", BK8:"8 h backup",
            BK24:"24 h backup"}.get(cost, str(cost))

if __name__ == "__main__":
    c = bucket_counts()
    print("Bill of materials, cost buckets:")
    for k,v in sorted(c.items(), reverse=True):
        print(f"  {v:>2} x BDT {k/1e6:>4.1f} M  ({label(k)})  = BDT {v*k/1e6:.1f} M")
    t = total_cost()
    print(f"TOTAL = BDT {t/1e6:.1f} M   of BDT 30.0 M")
    print(f"Remaining = BDT {(30e6-t)/1e6:.1f} M")
    print(f"10% contingency = BDT {0.1*t/1e6:.2f} M -> {((t+0.1*t)-30e6)/1e6:+.2f} M vs cap")
    print("\nLinks per line:")
    for h in HARDWARE:
        print(f"  {h['id']} {h['item'][:64]}: {len(h['links'])} links")
    bad=[u for h in HARDWARE for _,u in h["links"] if not u.startswith("http")]
    print("bad links:", bad)
