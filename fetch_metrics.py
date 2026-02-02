# fetch_metrics.py
import json, time, re, urllib.request, datetime, os

def get(url):
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return r.read()
        except:
            time.sleep(2)
    raise RuntimeError(f"Failed fetch: {url}")

def jget(url):
    return json.loads(get(url))

def asi_from_html(html):
    s = html.decode("utf-8", "ignore")
    m = re.search(r"Altcoin Season Index[^0-9]{0,400}(\d{1,3})", s, re.I)
    if not m:
        m = re.search(r"(\d{1,3})\s*/\s*100", s)
    v = int(m.group(1)) if m else None
    return v if v is not None and 0 <= v <= 100 else None

def load_hist():
    if os.path.exists("hist.json"):
        return json.loads(open("hist.json","r").read())
    return []

def save_hist(hist):
    open("hist.json","w").write(json.dumps(hist[-4000:]))

def nearest(hist, t):
    return min(hist, key=lambda x: abs(x["t"]-t)) if hist else None

def pct(a,b):
    return (a-b)/b*100 if b not in (None,0) else None

def main():
    now = int(time.time())
    CG = "https://api.coingecko.com/api/v3"
    BIN = "https://fapi.binance.com"

    bd = jget(f"{CG}/global")["data"]["market_cap_percentage"]["btc"]

    p = jget(f"{CG}/simple/price?ids=bitcoin,ethereum,solana,ripple&vs_currencies=usd")
    btc,eth,sol,xrp = p["bitcoin"]["usd"],p["ethereum"]["usd"],p["solana"]["usd"],p["ripple"]["usd"]
    alt = {"ETH":eth/btc,"SOL":sol/btc,"XRP":xrp/btc}

    oi = float(jget(f"{BIN}/fapi/v1/openInterest?symbol=BTCUSDT")["openInterest"])

    ls = jget(f"{BIN}/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=1")[0]
    ls = {"long":float(ls["longAccount"])*100,"short":float(ls["shortAccount"])*100}

    fo = jget(f"{BIN}/fapi/v1/allForceOrders?symbol=BTCUSDT&limit=1000")

    def sum_liq(sec):
        cut=(now-sec)*1000; L=S=0; n=0
        for o in fo:
            if o["time"]<cut: continue
            v=float(o["price"])*float(o["origQty"])
            if v<=0: continue
            n+=1
            if o["side"]=="SELL": L+=v
            if o["side"]=="BUY": S+=v
        return {"usd":L+S,"long_usd":L,"short_usd":S,"n":n}

    liq={"h1":sum_liq(3600),"h4":sum_liq(14400),"h24":sum_liq(86400)}

    asi = asi_from_html(get("https://www.blockchaincenter.net/en/altcoin-season-index/"))

    hist = load_hist()
    hist.append({"t":now,"BD":bd,"ASI":asi,"ALT":alt,"OI":oi})
    save_hist(hist)

    def snap(d): 
        return nearest(hist, now-int(d*86400)) or {}

    b1,b7,b30,b365 = snap(1),snap(7),snap(30),snap(365)

    out={
        "ts":datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "BD":{"v":bd,"d24":bd-b1.get("BD") if b1 else None,
              "d7_base":b7.get("BD"),"d7":bd-b7.get("BD") if b7 else None,
              "d30_base":b30.get("BD"),"d30":bd-b30.get("BD") if b30 else None,
              "d365_base":b365.get("BD"),"d365":bd-b365.get("BD") if b365 else None},
        "ASI":{"v":asi,"d24":asi-b1.get("ASI") if asi!=None and b1.get("ASI")!=None else None,
               "d7_base":b7.get("ASI"),"d7":asi-b7.get("ASI") if asi!=None and b7.get("ASI")!=None else None,
               "d30_base":b30.get("ASI"),"d30":asi-b30.get("ASI") if asi!=None and b30.get("ASI")!=None else None,
               "d365_base":b365.get("ASI"),"d365":asi-b365.get("ASI") if asi!=None and b365.get("ASI")!=None else None},
        "ALT":alt,
        "ALTd7":{k:pct(alt[k],b7.get("ALT",{}).get(k)) for k in alt},
        "ALTd30":{k:pct(alt[k],b30.get("ALT",{}).get(k)) for k in alt},
        "ALTd365":{k:pct(alt[k],b365.get("ALT",{}).get(k)) for k in alt},
        "OI":{"v":oi,"d24":pct(oi,b1.get("OI"))},
        "OId7":{"base":b7.get("OI"),"d":pct(oi,b7.get("OI"))},
        "OId30":{"base":b30.get("OI"),"d":pct(oi,b30.get("OI"))},
        "OId365":{"base":b365.get("OI"),"d":pct(oi,b365.get("OI"))},
        "LIQ":liq,
        "LS":ls
    }

    open("data.json","w").write(json.dumps(out))

if __name__=="__main__":
    main()