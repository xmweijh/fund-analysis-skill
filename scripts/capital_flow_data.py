"""公开资金面采集与计算。金额统一为人民币亿元；仅依赖标准库。"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CST = timezone(timedelta(hours=8))
SSE = "https://query.sse.com.cn/commonQuery.do"
SZSE = "https://www.szse.cn/api/report/ShowReport"
NAV = "https://api.fund.eastmoney.com/f10/lsjz"
FLOW = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
FLOW_SNAPSHOT = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get"


def number(v):
    try:
        n = float(str(v).replace(",", ""))
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    temp.replace(path)


class PublicClient:
    """单次请求，无自动重试；同主机失败后暂停，已有原文可离线复用。"""
    def __init__(self, cache, offline=False):
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.audit, self.blocked = [], set()
        self.offline = offline

    def get(self, url, params, referer, key, reuse=True):
        full = url + "?" + urllib.parse.urlencode(params)
        target = self.cache / key
        host = urllib.parse.urlsplit(url).hostname
        entry = {"url": full, "raw_file": str(target.resolve())}
        if reuse and target.exists():
            body = target.read_bytes()
            entry.update(mode="缓存复用", fetched_at=datetime.fromtimestamp(target.stat().st_mtime, CST).isoformat())
        elif self.offline:
            entry.update(mode="缓存缺失",error="离线重建，未请求网络；无有效原文缓存")
            self.audit.append(entry)
            return None
        elif host in self.blocked:
            entry.update(mode="跳过", error="该主机本轮已失败，暂停请求")
            self.audit.append(entry)
            return None
        else:
            try:
                request = urllib.request.Request(full, headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36", "Referer":referer})
                with urllib.request.urlopen(request, timeout=22) as response:
                    body = response.read()
                target.write_bytes(body)
                entry.update(mode="本轮抓取", fetched_at=datetime.now(CST).isoformat())
                time.sleep(.16)
            except Exception as exc:
                self.blocked.add(host)
                entry.update(mode="失败", error=f"{type(exc).__name__}: {exc}")
                self.audit.append(entry)
                print(f"暂停 {host}: {type(exc).__name__}", flush=True)
                return None
        entry["sha256"] = hashlib.sha256(body).hexdigest()
        self.audit.append(entry)
        return body

    def json(self, *args, **kwargs):
        body = self.get(*args, **kwargs)
        if body is None:
            return None
        try:
            return json.loads(body)
        except (ValueError, UnicodeDecodeError):
            self.audit[-1]["error"] = "响应不是有效JSON"
            self.blocked.add(urllib.parse.urlsplit(args[0]).hostname)
            return None


def parse_szse_xlsx(body):
    """不信任XLSX的dimension；交易所文件可能写A1但实际含数万行。"""
    ns = {"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    output = {}
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            shared = ["".join(x.itertext()) for x in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("s:si", ns)]
        for name in z.namelist():
            if not name.startswith("xl/worksheets/sheet") or not name.endswith(".xml"):
                continue
            for row in ET.fromstring(z.read(name)).findall("s:sheetData/s:row", ns):
                cells = {}
                for cell in row.findall("s:c", ns):
                    col = "".join(c for c in cell.attrib.get("r", "") if c.isalpha())
                    if cell.attrib.get("t") == "inlineStr":
                        val = "".join(x.text or "" for x in cell.findall(".//s:t", ns))
                    else:
                        val = cell.findtext("s:v", "", ns)
                        if cell.attrib.get("t") == "s":
                            val = shared[int(val)]
                    cells[col] = val.strip()
                day, code = cells.get("A", ""), cells.get("B", "")
                shares = number(cells.get("D"))
                if len(day) == 10 and day[4] == "-" and code.isdigit() and shares is not None:
                    output.setdefault(day, {})[code.zfill(6)] = {"shares":shares, "name":cells.get("C", ""), "source":"SZSE"}
    return output


def daily_estimate(previous, current, nav, prev_nav=None):
    """不同ETF不能共用净值。未知/折算嫌疑返回null，不按零处理。"""
    if previous is None or current is None or nav is None:
        return None, "份额或同日净值缺失"
    if min(previous, current) < 0 or nav <= 0:
        return None, "数值无效"
    if prev_nav and previous > 0:
        ratio = current / previous
        if abs(nav / prev_nav - 1) > .25 and abs(ratio - 1) > .25 and abs(ratio * nav / prev_nav - 1) < .15:
            return None, "疑似份额折算，待核公告"
    return (current - previous) * nav / 1e8, None


def strict_sum(values):
    return sum(values) if values and all(x is not None for x in values) else None


def parse_market_flow(document, code, as_of):
    """历史路由15列、备用快照6列；不把一条快照扩展为多日历史。"""
    if not isinstance(document,dict) or document.get("rc",0) != 0:
        return {}
    payload = document.get("data")
    if not isinstance(payload,dict) or str(payload.get("code")) != code:
        return {}
    output = {}
    for line in payload.get("klines",[]):
        if not isinstance(line,str):
            continue
        columns = line.split(",")
        if len(columns) < 6:
            continue
        day = columns[0]
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        amount = number(columns[1])
        if day <= as_of and amount is not None:
            output[day] = {"flow":amount/1e8,"ratio":number(columns[6]) if len(columns)>6 else None}
    return output


def fetch_market_flow(client, code, as_of):
    params = {"lmt":0,"klt":101,"fields1":"f1,f2,f3,f7",
              "fields2":"f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
              "secid":f"{'1' if code.startswith(('5','6')) else '0'}.{code}"}
    document = client.json(FLOW,params,"https://data.eastmoney.com/",f"etf_market_flow_{code}_{as_of}.json")
    history = parse_market_flow(document,code,as_of)
    if as_of in history:
        return history
    snapshot = client.json(FLOW_SNAPSHOT,{**params,"lmt":120},"https://data.eastmoney.com/",f"etf_market_snapshot_{code}_{as_of}.json")
    for day, row in parse_market_flow(snapshot,code,as_of).items():
        history.setdefault(day,row)
    return history


def national_quantity_bounds(evidence, as_of):
    """匿名期末持仓以全基金总份额作上界；不是卖出金额估计。"""
    if evidence.get("as_of", "9999") > as_of:
        return None
    result = {**evidence,"rows":[]}
    for original in evidence.get("rows",[]):
        if max(original["previous_source"]["published_at"],original["current_source"]["published_at"]) > as_of:
            continue
        row = dict(original)
        old = strict_sum([number(row.get("huijin_investment_shares")),number(row.get("huijin_asset_shares"))])
        cap = number(row.get("current_total_shares"))
        row["previous_confirmed_shares"] = old
        row["minimum_decrease_shares"] = max(0,old-cap) if old is not None and cap is not None and min(old,cap)>=0 and row.get("split_change")==0 else None
        row["current_confirmed_shares"] = None
        result["rows"].append(row)
    return result if result["rows"] else None


def window_stats(series, dates, n, field="flow"):
    """要求完整的n个市场观测日，不跨缺口缩短窗口。"""
    selected = dates[-n:]
    values = [series.get(d, {}).get(field) for d in selected]
    valid = sum(v is not None for v in values)
    total = strict_sum(values) if len(selected) == n else None
    return {"value":total, "valid":valid, "required":n,
            "start":selected[0] if selected else None, "end":selected[-1] if selected else None}


def build_direction(config, products, dates):
    items = [products[c] for c in config["codes"]]
    daily = {}
    for d in dates:
        rows = [p["daily"].get(d, {}) for p in items]
        flow = strict_sum([x.get("flow") for x in rows])
        market_flow = strict_sum([x.get("market_flow") for x in rows])
        aum = strict_sum([x.get("aum") for x in rows])
        base = strict_sum([x.get("previous_aum") for x in rows])
        daily[d] = {"flow":flow, "market_flow":market_flow,"aum":aum, "previous_aum":base,
                    "intensity": flow / base * 100 if flow is not None and base and base > 0 else None,
                    "market_intensity":market_flow / base * 100 if market_flow is not None and base and base > 0 else None,
                    "reason":next((x.get("reason") for x in rows if x.get("reason")), None)}
    windows, market_windows = {}, {}
    for n in (1, 5, 20):
        w = window_stats(daily, dates, n)
        start_base = daily.get(w["start"], {}).get("previous_aum")
        w["intensity"] = w["value"] / start_base * 100 if w["value"] is not None and start_base and start_base > 0 else None
        selected = [daily.get(d, {}).get("flow") for d in dates[-n:]]
        w["positive_days"] = sum(x > 0 for x in selected if x is not None)
        windows[str(n)] = w
        m = window_stats(daily,dates,n,"market_flow")
        m["intensity"] = m["value"] / start_base * 100 if m["value"] is not None and start_base and start_base > 0 else None
        m["positive_days"] = sum(daily.get(d,{}).get("market_flow") is not None and daily[d]["market_flow"] > 0 for d in dates[-n:])
        market_windows[str(n)] = m
    return {**config, "daily":daily, "windows":windows,"market_windows":market_windows}


def collect(cache, as_of, universe, offline=False):
    client = PublicClient(cache,offline)
    cfg = json.loads(Path(universe).read_text(encoding="utf-8"))
    codes = [c for x in cfg["directions"] for c in x["codes"]]
    if len(codes) != len(set(codes)):
        raise ValueError("ETF样本代码不能重复归类")
    start = (date.fromisoformat(as_of) - timedelta(days=65)).isoformat()
    navs = {}
    # 510300为市场日期锚；正式日历来自其实际净值记录，不以周一至周五代替交易日。
    for i, code in enumerate(codes):
        doc = client.json(NAV, {"fundCode":code,"pageIndex":1,"pageSize":100,"startDate":start,"endDate":as_of},
                          "https://fundf10.eastmoney.com/", f"nav_{code}_{as_of}.json")
        navs[code] = {x["FSRQ"]:{"nav":number(x.get("DWJZ")),"return_pct":number(x.get("JZZZL")),"event":x.get("FHFCZ") or x.get("FHSP")} for x in (doc or {}).get("Data", {}).get("LSJZList", []) if x.get("FSRQ", "") <= as_of}
        # 接口可能把pageSize上限固定为20；按响应分页，不能假定请求100就得到100。
        for page in range(2, 4):
            if len(navs[code]) >= 21 or not doc or doc.get("TotalCount",0) <= len(navs[code]):
                break
            extra = client.json(NAV,{"fundCode":code,"pageIndex":page,"pageSize":20,"startDate":start,"endDate":as_of},
                                "https://fundf10.eastmoney.com/",f"nav_{code}_{as_of}_p{page}.json")
            for x in (extra or {}).get("Data",{}).get("LSJZList",[]):
                if x.get("FSRQ", "") <= as_of:
                    navs[code][x["FSRQ"]] = {"nav":number(x.get("DWJZ")),"return_pct":number(x.get("JZZZL")),"event":x.get("FHFCZ") or x.get("FHSP")}
        if i % 10 == 0:
            print(f"净值 {i+1}/{len(codes)}", flush=True)
    dates = sorted(navs.get("510300", {}))[-21:]
    if len(dates) < 2:
        raise ValueError("未取得日期锚净值，不能构建同日资金方向")
    shares = {}
    for i, day in enumerate(dates):
        doc = client.json(SSE, {"isPagination":"true","pageHelp.pageSize":10000,"pageHelp.pageNo":1,
                               "pageHelp.beginPage":1,"pageHelp.cacheSize":1,"pageHelp.endPage":1,
                               "sqlId":"COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L","STAT_DATE":day},
                          "https://www.sse.com.cn/", f"sse_{day}.json")
        rows = (doc or {}).get("result", [])
        shares[day] = {x["SEC_CODE"]:{"shares":number(x["TOT_VOL"]) * 10000,"name":x["SEC_NAME"],"source":"SSE"}
                       for x in rows if x.get("STAT_DATE") == day and number(x.get("TOT_VOL")) is not None}
        if i % 5 == 0:
            print(f"沪市份额 {i+1}/{len(dates)}", flush=True)
    body = client.get(SZSE, {"SHOWTYPE":"xlsx","CATALOGID":"scsj_fund_jjgm","TABKEY":"tab1",
                            "txtStart":dates[0],"txtEnd":dates[-1],"jjlb":"ETF"},
                      "https://www.szse.cn/market/fund/volume/etf/index.html", f"szse_{dates[0]}_{dates[-1]}.xlsx")
    if body:
        try:
            for d, row in parse_szse_xlsx(body).items():
                if d in shares:
                    shares[d].update(row)
        except (ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
            client.audit.append({"mode":"解析失败","error":str(exc),"url":SZSE})
    products = {}
    for code in codes:
        market_daily = fetch_market_flow(client,code,as_of)
        daily = {}
        for i, d in enumerate(dates):
            row = shares.get(d, {}).get(code, {})
            prev_d = dates[i-1] if i else None
            prev = shares.get(prev_d, {}).get(code, {})
            nv = navs[code].get(d, {})
            pnv = navs[code].get(prev_d, {})
            s, ps, v, pv = row.get("shares"), prev.get("shares"), nv.get("nav"), pnv.get("nav")
            flow, reason = daily_estimate(ps, s, v, pv)
            if nv.get("event"):
                flow, reason = None, "分红/折算事件字段非空，待核公告"
            daily[d] = {"shares":s,"nav":v,"flow":flow,"reason":reason,
                        "market_flow":market_daily.get(d,{}).get("flow"),"market_ratio":market_daily.get(d,{}).get("ratio"),
                        "aum":s*v/1e8 if s is not None and v else None,
                        "previous_aum":ps*pv/1e8 if ps is not None and pv else None,
                        "return_pct":nv.get("return_pct")}
        names = [shares[d][code]["name"] for d in dates if code in shares.get(d, {})]
        products[code] = {"code":code,"name":names[-1] if names else "名称待核验", "daily":daily,
                          "nav_source":f"https://fundf10.eastmoney.com/jjjz_{code}.html"}
    observation_dates = dates[1:]
    directions = [build_direction(x, products, observation_dates) for x in cfg["directions"]]
    print("ETF申赎及二级市场主力资金已处理", flush=True)
    evidence_file = ROOT/"assets/capital-flow-national-evidence.json"
    national_evidence = national_quantity_bounds(json.loads(evidence_file.read_text(encoding="utf-8")),as_of) if evidence_file.exists() else None
    return {"schema":"capital-flow-v1","requested_as_of":as_of,"as_of":dates[-1],
            "generated_at":datetime.now(CST).isoformat(),"dates":observation_dates,
            "scope":cfg["scope"],"products":products,"directions":directions,
            "national":{"codes":cfg["national_observation_codes"],"scope":cfg["national_scope"],
                        "events":[e for e in cfg["events"] if e.get("published_at",e["date"]) <= as_of],
                        "quantity_bounds":national_evidence,"daily_confirmed_net_buy":None,"current_holdings_verified":False},
            "audit":client.audit,
            "reference":{"url":"https://github.com/digger-yu/etf","used":"参考方向排行、时间热图与趋势交互；不复用其历史数据，不执行其代码。",
                         "findings":["公开JSON截至2025-07-08，不能用于当前方向判断。","汇总份额乘代表ETF净值不等于逐基金资产规模。","资产规模差额包含价格变动，不能直接标为资金净流入。","排除白银LOF估算份额，不混入ETF申赎。"]}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--universe", type=Path, default=ROOT/"assets/capital-flow-universe.json")
    ap.add_argument("--offline", action="store_true", help="只读取原文缓存，绝不联网")
    args = ap.parse_args()
    date.fromisoformat(args.as_of)
    data = collect(args.cache_dir,args.as_of,args.universe,args.offline)
    save_json(args.output,data)
    print(json.dumps({"as_of":data["as_of"],"directions":len(data["directions"]),"products":len(data["products"]),
                      "main_flow_products":sum(any(r.get("market_flow") is not None for r in p["daily"].values()) for p in data["products"].values()),"output":str(args.output)},ensure_ascii=False))


if __name__ == "__main__":
    main()
