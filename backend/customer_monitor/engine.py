"""
客户风险监控引擎
- 单个客户洗钱风险画像
- 多维度相似度 + LPA标签传播 团伙识别
"""
from collections import defaultdict
from datetime import datetime
import random
from backend.database import get_connection

HIGH_RISK_COUNTRIES = [
    "伊朗", "朝鲜", "缅甸", "叙利亚", "也门", "阿富汗", "伊拉克",
    "尼日利亚", "菲律宾", "土耳其", "阿联酋", "越南",
]
HIGH_RISK_OCCUPATIONS = ["个体工商户", "自由职业者", "企业高管"]
CHANNEL_RISK = {"柜面": 5, "网银": 10, "手机银行": 15, "代销": 20, "ATM": 10}


class CustomerMonitor:

    def profile(self, customer_id: str) -> dict:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customer WHERE customer_id = ?", (customer_id,))
        cust = cursor.fetchone()
        if not cust:
            conn.close()
            return {"status": "error", "message": f"客户 {customer_id} 不存在"}
        cust = dict(cust)
        cursor.execute("SELECT * FROM trans_record WHERE customer_id = ? ORDER BY transaction_date DESC", (customer_id,))
        transactions = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM account WHERE customer_id = ?", (customer_id,))
        accounts = [dict(r) for r in cursor.fetchall()]
        conn.close()

        tags = []
        if cust.get("occupation") in HIGH_RISK_OCCUPATIONS:
            tags.append({"label": "高风险职业", "color": "red"})
        if cust.get("risk_level") == "高":
            tags.append({"label": "高原始风险等级", "color": "red"})
        elif cust.get("risk_level") == "中":
            tags.append({"label": "中原始风险等级", "color": "orange"})
        if cust.get("nationality") in HIGH_RISK_COUNTRIES:
            tags.append({"label": f"国籍:{cust['nationality']}", "color": "red"})
        elif cust.get("nationality") != "中国":
            tags.append({"label": "非中国居民", "color": "orange"})
        if not cust.get("id_number"):
            tags.append({"label": "证件信息缺失", "color": "red"})

        large_count = sum(1 for t in transactions if (t.get("amount") or 0) > 1000000)
        if large_count > 0:
            tags.append({"label": f"大额交易{large_count}笔", "color": "orange" if large_count < 5 else "red"})
        cross = sum(1 for t in transactions if t.get("currency", "CNY") != "CNY")
        if cross > 0:
            tags.append({"label": f"跨境交易{cross}笔", "color": "orange" if cross < 5 else "red"})
        neg = sum(1 for t in transactions if (t.get("amount") or 0) < 0)
        if neg > 0:
            tags.append({"label": f"异常金额{neg}笔", "color": "red"})

        occ_score = 30 if cust.get("occupation") in HIGH_RISK_OCCUPATIONS else 0
        rl_score = 30 if cust.get("risk_level") == "高" else 15 if cust.get("risk_level") == "中" else 0
        idt_score = 10 if cust.get("id_type") == "护照" else 0
        cs = min(100, occ_score + rl_score + idt_score)
        cs_details = [
            {"rule": "职业风险评估", "desc": f"职业: {cust.get('occupation','未知')}", "score": occ_score, "max": 30},
            {"rule": "原始风险等级", "desc": f"等级: {cust.get('risk_level','低')}", "score": rl_score, "max": 30},
            {"rule": "证件类型", "desc": f"类型: {cust.get('id_type','身份证')}", "score": idt_score, "max": 10},
        ]

        nation = cust.get("nationality", "中国")
        if nation in HIGH_RISK_COUNTRIES:
            gs = 80
            gs_detail = f"国籍({nation})在FATF高风险名单中"
        elif nation != "中国":
            gs = 30
            gs_detail = f"国籍({nation})为非中国居民"
        else:
            gs = 5
            gs_detail = "中国居民,地域风险较低"
        gs_details = [{"rule": "国籍/地域", "desc": gs_detail, "score": gs, "max": 80}]

        acct_base = min(len(accounts) * 5, 25)
        ps_details = [{"rule": "账户数量", "desc": f"持有{len(accounts)}个账户", "score": acct_base, "max": 25}]
        high_prod_score = 0
        conn2 = get_connection(); c2 = conn2.cursor()
        for a in accounts:
            pid = a.get("product_id")
            if pid:
                c2.execute("SELECT product_type FROM product WHERE product_id = ?", (pid,))
                row = c2.fetchone()
                if row and row["product_type"] in ("私募-股票多头", "私募-量化对冲", "专户-权益"):
                    high_prod_score += 20
        conn2.close()
        ps = min(100, acct_base + high_prod_score)
        if high_prod_score > 0:
            ps_details.append({"rule": "高风险产品", "desc": f"持有{high_prod_score//20}只高风险产品(私募/专户权益)", "score": high_prod_score, "max": 75})

        if not transactions:
            ts = 5
            ts_details = [{"rule": "无交易记录", "desc": "客户无交易", "score": 5, "max": 100}]
        else:
            freq_score = min(len(transactions) / 5, 15)
            large_score = min(sum(1 for t in transactions if (t.get("amount") or 0) > 1000000) * 8, 40)
            cross_score = min(sum(1 for t in transactions if t.get("currency", "CNY") != "CNY") * 8, 30)
            neg_score = min(sum(1 for t in transactions if (t.get("amount") or 0) < 0) * 10, 20)
            ts = min(100, freq_score + large_score + cross_score + neg_score)
            large_cnt = sum(1 for t in transactions if (t.get("amount") or 0) > 1000000)
            cross_cnt = sum(1 for t in transactions if t.get("currency", "CNY") != "CNY")
            neg_cnt = sum(1 for t in transactions if (t.get("amount") or 0) < 0)
            ts_details = [
                {"rule": "交易频率", "desc": f"共{len(transactions)}笔交易", "score": round(freq_score,1), "max": 15},
                {"rule": "大额交易", "desc": f"{large_cnt}笔大于100万", "score": large_score, "max": 40},
                {"rule": "跨境交易", "desc": f"{cross_cnt}笔非人民币", "score": cross_score, "max": 30},
                {"rule": "异常金额", "desc": f"{neg_cnt}笔负数金额", "score": neg_score, "max": 20},
            ]

        if not transactions:
            chs = 5
            chs_details = [{"rule": "无交易记录", "desc": "客户无交易", "score": 5, "max": 100}]
        else:
            channels = list(set(t.get("channel") for t in transactions))
            max_ch = max(CHANNEL_RISK.get(c, 10) for c in channels)
            chs = min(100, max_ch + len(channels) * 5)
            chs_details = [
                {"rule": "最高风险渠道", "desc": f"渠道: {', '.join(channels[:3])}", "score": max_ch, "max": 20},
                {"rule": "渠道多样性", "desc": f"使用{len(channels)}种渠道", "score": len(channels) * 5, "max": 40},
            ]

        dims = {
            "客户属性": {"score": round(cs,1), "weight": "25%", "details": cs_details},
            "地域风险": {"score": round(gs,1), "weight": "20%", "details": gs_details},
            "产品风险": {"score": round(ps,1), "weight": "20%", "details": ps_details},
            "交易行为": {"score": round(ts,1), "weight": "25%", "details": ts_details},
            "渠道风险": {"score": round(chs,1), "weight": "10%", "details": chs_details},
        }
        overall = round(sum(d["score"] * int(d["weight"].replace("%","")) / 100 for d in dims.values()), 1)
        level = "低" if overall <= 30 else "中" if overall <= 60 else "高" if overall <= 80 else "最高"

        monthly = defaultdict(float)
        for t in transactions:
            dt = t.get("transaction_date", "")[:7]
            if dt: monthly[dt] += abs(t.get("amount") or 0)
        trend = [{"month": k, "amount": round(v, 2)} for k, v in sorted(monthly.items())[-12:]]

        return {
            "status": "ok", "customer": cust,
            "stats": {"total_txn": len(transactions),
                      "total_amount": round(sum(abs(t.get("amount") or 0) for t in transactions), 2),
                      "large_txn": large_count, "cross_border": cross, "accounts": len(accounts)},
            "overall_score": overall, "risk_level": level,
            "tags": tags, "dimensions": dims, "trend": trend,
            "transactions": transactions[:20],
        }

    def network_analysis(self, min_amount: float = 0) -> dict:
        """多维度相似度 + LPA标签传播 团伙识别"""
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT * FROM trans_record WHERE counterparty_info IS NOT NULL AND counterparty_info != ''")
        transactions = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM customer")
        customers = {c["customer_id"]: dict(c) for c in cursor.fetchall()}
        conn.close()

        transactions = [t for t in transactions if (t.get("amount") or 0) >= min_amount]
        active_customers = set(t["customer_id"] for t in transactions)

        def extract_province(addr):
            if not addr: return ""
            for p in ["北京","上海","广东","深圳","四川","湖北","浙江","江苏","福建","山东",
                      "河北","河南","湖南","陕西","云南","贵州","广西","辽宁","吉林","黑龙江",
                      "重庆","天津","海南","甘肃","宁夏","青海","西藏","新疆","内蒙古","安徽","江西","山西"]:
                if p in addr: return p
            return addr[:2] if addr else ""

        # 预计算客户特征
        c_txns = defaultdict(list)
        for t in transactions: c_txns[t["customer_id"]].append(t)

        profiles = {}
        for cid in active_customers:
            txns = c_txns[cid]; cust = customers.get(cid, {})
            amounts = [abs(t.get("amount") or 0) for t in txns]
            dates = [t.get("transaction_date", "") for t in txns if t.get("transaction_date")]
            cps = set(t.get("counterparty_info", "") for t in txns if t.get("counterparty_info"))
            profiles[cid] = {
                "avg_amount": sum(amounts)/len(amounts) if amounts else 0,
                "txn_count": len(txns),
                "province": extract_province(cust.get("address", "")),
                "counterparties": cps,
                "dates": sorted(dates),
            }

        customer_list = list(active_customers); n = len(customer_list)
        if n < 2:
            return {"status":"ok","nodes":[],"links":[],"gangs":[],
                    "stats":{"total_customers":n,"total_edges":0,"total_gangs":0,"max_gang_size":0}}

        # 多维度相似度计算
        weighted_edges = {}
        edge_details = {}
        for i in range(n):
            for j in range(i+1, n):
                a, b = customer_list[i], customer_list[j]
                pa, pb = profiles[a], profiles[b]

                cpa, cpb = pa["counterparties"], pb["counterparties"]
                shared = cpa & cpb
                cp_sim = len(shared) / max(len(cpa | cpb), 1)

                avg_a, avg_b = pa["avg_amount"], pb["avg_amount"]
                max_avg = max(avg_a, avg_b, 1)
                amount_sim = 1 - min(abs(avg_a - avg_b) / max_avg, 1)

                geo_sim = 1.0 if pa["province"] and pa["province"] == pb["province"] else 0.0

                time_sim = 0.0
                if pa["dates"] and pb["dates"]:
                    da, db = pa["dates"], pb["dates"]
                    close = 0
                    for d1 in da:
                        for d2 in db:
                            try:
                                dt1 = datetime.strptime(d1[:10], "%Y-%m-%d")
                                dt2 = datetime.strptime(d2[:10], "%Y-%m-%d")
                                if abs((dt1-dt2).days) <= 7: close += 1
                            except: pass
                    time_sim = min(1.0, close / max(len(da), len(db), 1))

                total_weight = cp_sim * 0.35 + amount_sim * 0.25 + geo_sim * 0.20 + time_sim * 0.20

                if total_weight > 0.35:
                    key = (a, b) if a < b else (b, a)
                    weighted_edges[key] = total_weight
                    edge_details[key] = {"cp_shared":round(cp_sim,3),"amount_sim":round(amount_sim,3),
                                         "geo_sim":round(geo_sim,3),"time_sim":round(time_sim,3),
                                         "total":round(total_weight,3)}

        # LPA 标签传播
        node_to_idx = {cid: i for i, cid in enumerate(customer_list)}
        labels = list(range(n))
        neighbors = defaultdict(list)
        for (a, b), w in weighted_edges.items():
            ia, ib = node_to_idx[a], node_to_idx[b]
            neighbors[ia].append((ib, w)); neighbors[ib].append((ia, w))

        for _ in range(50):
            changed = False
            order = list(range(n)); random.shuffle(order)
            for i in order:
                if not neighbors[i]: continue
                lw = defaultdict(float)
                for j, w in neighbors[i]: lw[labels[j]] += w
                if lw:
                    best = max(lw, key=lw.get)
                    if labels[i] != best: labels[i] = best; changed = True
            if not changed: break

        groups = defaultdict(set)
        for i, label in enumerate(labels): groups[label].add(customer_list[i])

        gangs, gang_members, gang_member_ids = [], {}, {}
        gang_idx = 0
        for g in groups.values():
            if 3 <= len(g) <= 15:
                gc = list(g)
                iw, ic = 0, 0
                for a in gc:
                    for b in gc:
                        if a < b and (a,b) in weighted_edges:
                            iw += weighted_edges[(a,b)]; ic += 1
                avg_sim = iw/ic if ic > 0 else 0
                density = ic / (len(gc)*(len(gc)-1)/2) if len(gc)>1 else 0
                risk = "高" if avg_sim > 0.7 or density > 0.7 else "中" if avg_sim > 0.45 or density > 0.4 else "低"
                gangs.append({"id":gang_idx,"name":f"团伙{gang_idx+1}","size":len(gc),"customers":[],
                              "density":round(density,2),"avg_similarity":round(avg_sim,3),
                              "risk":risk,"internal_edges":ic})
                gang_member_ids[gang_idx] = gc
                for cid in gc: gang_members[cid] = gang_idx
                gang_idx += 1
        gangs.sort(key=lambda g: (0 if g["risk"]=="高" else 1 if g["risk"]=="中" else 2, -g["size"]))

        # 节点
        node_ids = set()
        for (a,b) in weighted_edges: node_ids.add(a); node_ids.add(b)
        names = {}
        for cid in node_ids:
            c = customers.get(cid, {})
            names[cid] = {"name":c.get("name",cid),"risk":c.get("risk_level","低")}

        # 填充团伙成员详情
        for g in gangs:
            members = []
            for cid in gang_member_ids[g["id"]]:
                c = customers.get(cid, {})
                age = ""
                if c.get("birth_date"):
                    try:
                        bd = datetime.strptime(c["birth_date"], "%Y-%m-%d")
                        age = str((datetime.now()-bd).days//365) + "岁"
                    except: pass
                members.append({"id":cid,"name":c.get("name",""),"risk":c.get("risk_level","低"),
                                "age":age,"nationality":c.get("nationality",""),
                                "phone":c.get("phone",""),"address":(c.get("address","") or "")[:30],
                                "occupation":c.get("occupation","")})
            g["customers"] = members
            # 交易关联
            gc_set = set(gang_member_ids[g["id"]])
            rels = []
            for a in gc_set:
                for b in gc_set:
                    if a < b and (a,b) in edge_details:
                        det = edge_details[(a,b)]
                        cps = list(profiles[a]["counterparties"] & profiles[b]["counterparties"])
                        rels.append({"from":names.get(a,{}).get("name",a),
                                     "to":names.get(b,{}).get("name",b),
                                     "total_sim":det["total"],"cp_shared":det["cp_shared"],
                                     "amount_sim":det["amount_sim"],"geo_sim":det["geo_sim"],
                                     "time_sim":det["time_sim"],"counterparties":cps[:5]})
            g["transactions"] = sorted(rels, key=lambda x:-x["total_sim"])

        gang_colors = ["#e74c3c","#4a90d9","#e67e22","#2ecc71","#9b59b6"]
        nodes = [{"id":cid,"name":names.get(cid,{"name":cid})["name"],
                  "risk":names.get(cid,{"risk":"低"})["risk"],
                  "gang":gang_members.get(cid,-1),
                  "gangName":f"团伙{gang_members[cid]+1}" if cid in gang_members else "",
                  "gangColor":gang_colors[gang_members[cid]%len(gang_colors)] if cid in gang_members else "",
                  "symbolSize":min(60,15+len([e for e in weighted_edges if cid in e])*3)}
                 for cid in node_ids]
        links = [{"source":a,"target":b,"value":round(w,3)} for (a,b),w in weighted_edges.items()]

        return {"status":"ok","nodes":nodes,"links":links,"gangs":gangs,
                "stats":{"total_customers":len(node_ids),"total_edges":len(weighted_edges),
                         "total_gangs":len(gangs),"max_gang_size":max((g["size"] for g in gangs),default=0)}}

    def get_customer_list(self, limit=100):
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute("SELECT customer_id, name, risk_level, nationality FROM customer LIMIT ?", (limit,))
        rows = cursor.fetchall(); conn.close()
        return [dict(r) for r in rows]
