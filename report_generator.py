import json, math, os

OUTPUTS_PATH = "./outputs"
BRAND_COLORS = ["#6366F1","#F59E0B","#10B981","#EF4444",
                "#8B5CF6","#06B6D4","#F97316","#84CC16"]
INTENT_COLORS  = {
    "informational": "#6366F1",
    "features":      "#10B981",
    "situational":   "#EC4899",
    "purchase":      "#F97316",
}
INTENT_LABELS  = {
    "informational": "Informational",
    "features":      "Features",
    "situational":   "Situational",
    "purchase":      "Purchase",
}

def brand_color(i): return BRAND_COLORS[i % len(BRAND_COLORS)]

def _load(fname):
    p = f"{OUTPUTS_PATH}/{fname}"
    if not os.path.exists(p): return {}
    with open(p, encoding="utf-8") as f: return json.load(f)

# ── Dot badge ──────────────────────────────────────────────────────────────────
def _dot(name, color):
    return (f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{color}1A;border:1px solid {color}44;border-radius:12px;'
            f'padding:3px 9px;font-size:11px;font-weight:500;margin:2px">'
            f'<span style="width:7px;height:7px;border-radius:50%;'
            f'background:{color}"></span>{name}</span>')

def _render_session(brands_list, our_brand, competitors):
    if not brands_list:
        return '<span style="color:#475569;font-size:11px">—</span>'
    out = ""
    for b in brands_list:
        if b == our_brand:    out += _dot(b, "#6366F1")
        elif b in competitors: out += _dot(b, "#F59E0B")
        else:                  out += _dot(b, "#475569")
    return out

def _ibadge(intent):
    c = INTENT_COLORS.get(intent, "#475569")
    l = INTENT_LABELS.get(intent, intent.capitalize() if intent else "?")
    return (f'<span style="font-size:10px;font-weight:700;border-radius:10px;'
            f'padding:2px 8px;background:{c}22;color:{c};border:1px solid {c}44;'
            f'margin-right:5px">{l}</span>')

def _cbadge(cons):
    cc = {"HC":"#10B981","MC":"#F59E0B","DROP":"#EF4444"}.get(cons,"#475569")
    return (f'<span style="font-size:10px;font-weight:700;padding:2px 8px;'
            f'border-radius:8px;background:{cc}22;color:{cc};'
            f'border:1px solid {cc}44">{cons}</span>')

# ── Executive summary ──────────────────────────────────────────────────────────
def _exec_summary(scores, meta):
    brand = meta.get("brand_name","Your Brand")
    comps = meta.get("competitors",[])
    bd    = scores.get(brand,{})
    rate  = bd.get("mention_rate",0)
    sov   = bd.get("share_of_voice",0)
    bi    = bd.get("by_intent",{})
    cr    = {c: scores.get(c,{}).get("mention_rate",0) for c in comps}
    top_c = max(cr,key=cr.get) if cr else "competitors"
    top_r = cr.get(top_c,0)
    ipts  = {k:v.get("points",0) for k,v in bi.items()}
    best  = max(ipts,key=ipts.get) if ipts else "informational"
    worst = min(ipts,key=ipts.get) if ipts else "features"
    try:
        from groq import Groq
        from config import GROQ_API_KEY, GROQ_MODEL
        c2 = Groq(api_key=GROQ_API_KEY)
        p  = (f"3-sentence executive summary for AI Visibility Audit.\n"
              f"Brand:{brand} Rate:{rate}% SOV:{sov}% Top competitor:{top_c}@{top_r}%\n"
              f"Best intent:{best} Weakest:{worst}\n"
              f"Sentence 1: AI visibility. Sentence 2: vs {top_c}. "
              f"Sentence 3: intent gap. Factual, specific.")
        r  = c2.chat.completions.create(
            model=GROQ_MODEL,messages=[{"role":"user","content":p}],max_tokens=220)
        return r.choices[0].message.content.strip()
    except Exception:
        return (f"{brand} appeared in {rate}% of AI-generated responses, "
                f"capturing {sov}% share of voice. {top_c} is the primary competitor "
                f"at {top_r}%. Visibility is strongest in {best} and weakest in {worst}.")

# ── BLOCK 1: Brand profile ─────────────────────────────────────────────────────
def _block_brand(meta):
    brand    = meta.get("brand_name","Your Brand")
    category = meta.get("category","") or meta.get("industry","")
    industry = meta.get("industry","") or category
    desc     = meta.get("brand_summary","") or "Brand description will appear here."
    kws      = meta.get("keywords",[])
    kw_html  = "".join(
        f'<span style="background:#1E293B;border:1px solid #334155;border-radius:8px;'
        f'padding:3px 10px;font-size:11px;color:#94A3B8;margin:3px">{k}</span>'
        for k in kws[:80])

    cat_html = ""
    if category:
        cat_html = f"""
    <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">
      <span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:8px;
                   background:#6366F122;color:#6366F1;border:1px solid #6366F133">
        Category: {category}
      </span>
      {f'<span style="font-size:11px;font-weight:700;padding:3px 10px;border-radius:8px;background:#10B98122;color:#10B981;border:1px solid #10B98133">Industry: {industry}</span>' if industry and industry != category else ""}
    </div>"""

    return f"""
<div class="block">
  <div style="display:flex;align-items:flex-start;gap:20px">
    <div style="width:80px;height:80px;border-radius:12px;background:#1E293B;
                border:2px dashed #334155;display:flex;align-items:center;
                justify-content:center;flex-shrink:0;color:#475569;
                font-size:10px;text-align:center">Logo<br>Soon</div>
    <div style="flex:1">
      <div style="font-size:22px;font-weight:800;margin-bottom:4px">{brand}</div>
      {cat_html}
      <div style="font-size:13px;color:#94A3B8;line-height:1.65;margin-top:10px">{desc}</div>
    </div>
  </div>
  <div style="margin-top:18px;padding-top:16px;border-top:1px solid var(--border)">
    <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;
                letter-spacing:.07em;margin-bottom:8px">
      Keyword Pool — {len(kws)} terms (finalized from all scraped URLs)
    </div>
    <div style="display:flex;flex-wrap:wrap">{kw_html}</div>
  </div>
</div>"""

# A query is scored when at least one tracked brand appeared in 2+ of 3 sessions.
# This is the same rule used by analytics.py. Do not use consistency alone as the
# denominator because a query can be scored even when session brand sets differ.
def _is_scored(entry, all_brands):
    return any(entry.get("brands", {}).get(b, {}).get("appeared", False) for b in all_brands)

# ── BLOCK 2: Scoring overview ──────────────────────────────────────────────────
def _block_scoring(scores, meta, all_brands, n_total, parsed):
    brand  = meta.get("brand_name","Your Brand")
    rows   = ""
    for i, b in enumerate(all_brands):
        d   = scores.get(b,{})
        pts = d.get("points",0)
        pct = (pts/n_total*100) if n_total else 0
        col = brand_color(i)
        tag = " · Your Brand" if b == brand else ""
        rows += f"""
<div style="margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px">
    <span style="font-weight:600">{b}<span style="color:#475569;font-weight:400">{tag}</span></span>
    <span style="color:{col};font-weight:700">{pts} / {n_total} &nbsp;·&nbsp; {pct:.1f}%</span>
  </div>
  <div style="background:#1E293B;border-radius:6px;height:10px">
    <div style="background:{col};width:{min(pct,100):.1f}%;height:100%;border-radius:6px"></div>
  </div>
</div>"""

    # Others — count unique scored queries that had ANY untracked brand appear
    # Computed directly from parsed so it is never stale or over 100%
    other_query_count = sum(
        1 for r in parsed
        if _is_scored(r, all_brands) and r.get("others")
    )
    o_pct = (other_query_count / n_total * 100) if n_total else 0
    rows += f"""
<div style="margin-bottom:4px">
  <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:5px">
    <span style="font-weight:600;color:#475569">
      Others — queries where at least one untracked brand appeared
    </span>
    <span style="color:#475569;font-weight:700">
      {other_query_count} / {n_total} &nbsp;·&nbsp; {o_pct:.1f}%
    </span>
  </div>
  <div style="background:#1E293B;border-radius:6px;height:10px">
    <div style="background:#475569;width:{min(o_pct,100):.1f}%;height:100%;border-radius:6px"></div>
  </div>
</div>"""

    return f"""
<div class="block">
  <h2>Scoring Overview</h2>
  <div style="font-size:12px;color:#94A3B8;line-height:1.7;margin-bottom:18px;
              background:#6366F108;border:1px solid #6366F122;border-radius:8px;
              padding:12px 14px">
    <b style="color:var(--text)">Scoring rule:</b> A brand earns
    <b style="color:var(--text)">1 point</b> per query when it appears in
    <b style="color:var(--text)">2 or 3 out of 3</b> independent Gemini sessions.
    Appearing in only 1 session earns no point. Queries where all 3 sessions give
    different results are <b style="color:#EF4444">dropped</b> and not scored.
  </div>
  {rows}
</div>"""

# ── BLOCK 3: Brand flashcards ──────────────────────────────────────────────────
def _block_flashcards(scores, meta, all_brands, parsed):
    brand   = meta.get("brand_name","Your Brand")
    # Compute per-intent totals from the exact scored population used by analytics.
    it_tot  = {"informational":0,"features":0,"situational":0,"purchase":0}
    for r in parsed:
        if _is_scored(r, all_brands):
            it = r.get("intent","informational")
            if it in it_tot: it_tot[it] += 1

    cards = ""
    for i, b in enumerate(all_brands):
        d    = scores.get(b,{})
        pts  = d.get("points",0)
        rate = d.get("mention_rate",0)
        sov  = d.get("share_of_voice",0)
        tot  = (d.get("total_organic_queries") or d.get("total_queries") or 0)
        hc   = d.get("hc_queries",0)
        mc   = d.get("mc_queries",0)
        bi   = d.get("by_intent",{})
        col  = brand_color(i)
        tag  = "YOUR BRAND" if b == brand else "COMPETITOR"

        intent_rows = ""
        for intent, ic in INTENT_COLORS.items():
            b_pts  = bi.get(intent,{}).get("points",0)
            i_tot  = it_tot.get(intent,0)
            pct    = (b_pts/i_tot*100) if i_tot else 0
            lbl    = INTENT_LABELS.get(intent,intent)
            intent_rows += f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:9px">
  <span style="width:100px;font-size:11px;font-weight:600;color:{ic}">{lbl}</span>
  <span style="width:55px;font-size:12px;font-weight:700;color:var(--text)">{b_pts}/{i_tot}</span>
  <div style="flex:1;background:#1E293B;border-radius:4px;height:7px;overflow:hidden">
    <div style="background:{ic};width:{min(pct,100):.1f}%;height:100%;border-radius:4px"></div>
  </div>
  <span style="width:38px;font-size:11px;color:#94A3B8;text-align:right">{pct:.0f}%</span>
</div>"""

        cards += f"""
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:14px;
            border-top:4px solid {col};padding:20px">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              margin-bottom:16px">
    <div>
      <div style="font-size:15px;font-weight:800;margin-bottom:4px">{b}</div>
      <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:8px;
                   background:{col}22;color:{col}">{tag}</span>
    </div>
    <div style="text-align:right">
      <div style="font-size:28px;font-weight:900;color:{col};line-height:1">
        {pts}<span style="font-size:13px;color:#475569;font-weight:400">/{tot}</span>
      </div>
      <div style="font-size:10px;color:#475569">queries appeared in</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:16px">
    <div style="text-align:center;background:#0F172A;border-radius:8px;padding:8px">
      <div style="font-size:17px;font-weight:700;color:{col}">{rate:.1f}%</div>
      <div style="font-size:10px;color:#475569">Mention Rate</div>
    </div>
    <div style="text-align:center;background:#0F172A;border-radius:8px;padding:8px">
      <div style="font-size:17px;font-weight:700;color:{col}">{sov:.1f}%</div>
      <div style="font-size:10px;color:#475569">Share of Voice</div>
    </div>
    <div style="text-align:center;background:#0F172A;border-radius:8px;padding:8px">
      <div style="font-size:17px;font-weight:700;color:#10B981">{hc}
        <span style="font-size:11px;color:#475569">+</span>
        <span style="color:#F59E0B">{mc}</span>
      </div>
      <div style="font-size:10px;color:#475569">HC + MC</div>
    </div>
  </div>
  <div style="border-top:1px solid var(--border);padding-top:12px">
    <div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;
                letter-spacing:.07em;margin-bottom:10px">
      Intent Breakdown &nbsp;
      <span style="font-weight:400;text-transform:none">
        (appeared / total queries in that intent)
      </span>
    </div>
    {intent_rows}
  </div>
</div>"""

    return f"""
<div class="block">
  <h2 style="margin-bottom:16px">Brand Score Cards</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px">
    {cards}
  </div>
</div>"""

# ── Visual Analytics block ─────────────────────────────────────────────────────
def _visual_analytics(scores, all_brands):
    # ── SOV donut — CSS conic-gradient (print-safe, no canvas) ──────────────
    sov_vals  = [scores.get(b,{}).get("share_of_voice",0) for b in all_brands]
    total_sov = sum(sov_vals) or 100
    cum, stops = 0, []
    for i, val in enumerate(sov_vals):
        pct = val / total_sov * 100
        col = brand_color(i)
        stops.append(f"{col} {cum:.1f}% {cum+pct:.1f}%")
        cum += pct
    gradient = "conic-gradient(" + ",".join(stops) + ")"

    legend_html = ""
    for i, b in enumerate(all_brands):
        sov = scores.get(b,{}).get("share_of_voice",0)
        col = brand_color(i)
        legend_html += (
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'margin-bottom:7px;font-size:12px">'
            f'<span style="width:12px;height:12px;border-radius:50%;'
            f'background:{col};flex-shrink:0"></span>'
            f'<span style="flex:1">{b}</span>'
            f'<span style="color:{col};font-weight:700">{sov:.1f}%</span></div>'
        )

    donut_html = (
        f'<div style="display:flex;align-items:center;gap:20px;flex-wrap:wrap">'
        f'<div style="position:relative;width:150px;height:150px;flex-shrink:0">'
        f'<div style="width:150px;height:150px;border-radius:50%;background:{gradient}"></div>'
        f'<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
        f'width:84px;height:84px;border-radius:50%;background:var(--bg-card)"></div>'
        f'</div><div style="flex:1;min-width:140px">{legend_html}</div></div>'
    )

    # ── Bar chart — inline SVG (print-safe, no canvas) ───────────────────────
    pts     = [scores.get(b,{}).get("points",0)       for b in all_brands]
    rates   = [scores.get(b,{}).get("mention_rate",0) for b in all_brands]
    max_val = max(max(pts, default=1), 1)
    n       = len(all_brands)
    bar_w   = max(32, min(56, 280 // max(n,1)))
    gap     = max(14, min(26, 140 // max(n,1)))
    pad_l   = 36
    pad_b   = 38
    chart_h = 210
    chart_w = pad_l + n * (bar_w * 2 + gap) + gap
    plot_h  = chart_h - pad_b

    grid = ""
    for gv in [25, 50, 75, 100]:
        y = chart_h - pad_b - int(gv / max_val * plot_h)
        if 0 < y < chart_h:
            grid += (
                f'<line x1="{pad_l}" y1="{y}" x2="{chart_w}" y2="{y}" '
                f'stroke="#1A2035" stroke-width="1" stroke-dasharray="4 3"/>'
                f'<text x="{pad_l-4}" y="{y+4}" text-anchor="end" '
                f'font-size="9" fill="#475569">{gv}</text>'
            )

    bars_svg = ""
    for i, (b, pt, rt) in enumerate(zip(all_brands, pts, rates)):
        x    = pad_l + gap + i * (bar_w * 2 + gap)
        col  = brand_color(i)
        h_pt = max(2, int(pt / max_val * plot_h))
        h_rt = max(2, int(rt / 100 * plot_h))
        y_pt = chart_h - pad_b - h_pt
        y_rt = chart_h - pad_b - h_rt
        lbl  = b[:10] + ("\u2026" if len(b) > 10 else "")
        bars_svg += (
            f'<rect x="{x}" y="{y_pt}" width="{bar_w-2}" height="{h_pt}" '
            f'fill="{col}" rx="4" opacity="0.95"/>'
            f'<rect x="{x+bar_w+2}" y="{y_rt}" width="{bar_w-2}" height="{h_rt}" '
            f'fill="{col}" rx="4" opacity="0.45"/>'
            f'<text x="{x+bar_w//2-1}" y="{y_pt-5}" text-anchor="middle" '
            f'font-size="9" fill="{col}" font-weight="700">{pt}</text>'
            f'<text x="{x+bar_w+2+bar_w//2-1}" y="{y_rt-5}" text-anchor="middle" '
            f'font-size="9" fill="{col}">{rt:.0f}%</text>'
            f'<text x="{x+bar_w}" y="{chart_h-pad_b+14}" text-anchor="middle" '
            f'font-size="10" fill="#94A3B8">{lbl}</text>'
        )

    bar_html = (
        f'<svg width="100%" viewBox="0 0 {chart_w} {chart_h}" '
        f'style="overflow:visible;display:block;max-height:220px">'
        f'{grid}'
        f'<line x1="{pad_l}" y1="{chart_h-pad_b}" x2="{chart_w}" '
        f'y2="{chart_h-pad_b}" stroke="#334155" stroke-width="1"/>'
        f'{bars_svg}</svg>'
        f'<div style="display:flex;gap:16px;font-size:11px;margin-top:6px;color:#94A3B8">'
        f'<span><span style="display:inline-block;width:10px;height:10px;background:#6366F1;'
        f'border-radius:2px;margin-right:4px;opacity:0.95"></span>Points (solid)</span>'
        f'<span><span style="display:inline-block;width:10px;height:10px;background:#6366F1;'
        f'border-radius:2px;margin-right:4px;opacity:0.45"></span>Mention Rate % (faded)</span>'
        f'</div>'
    )

    return (
        f'<div class="block" style="margin-bottom:20px">'
        f'<h2 style="margin-bottom:20px">Visual Analytics</h2>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start">'
        f'<div><div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:14px">Share of Voice (SOV)</div>{donut_html}</div>'
        f'<div><div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-bottom:14px">Points &amp; Mention Rate</div>{bar_html}</div>'
        f'</div></div>'
    )

# ── Intent distribution ────────────────────────────────────────────────────────
def _intent_dist(parsed, n_total, all_brands):
    counts = {"informational":0,"features":0,"situational":0,"purchase":0}
    for r in parsed:
        if _is_scored(r, all_brands):
            it = r.get("intent","informational")
            if it in counts: counts[it] += 1
    rows = ""
    for intent, count in counts.items():
        pct = (count/n_total*100) if n_total else 0
        col = INTENT_COLORS.get(intent,"#475569")
        lbl = INTENT_LABELS.get(intent,intent)
        rows += f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
  <span style="width:110px;font-size:12px;font-weight:600;color:{col}">{lbl}</span>
  <div style="flex:1;background:#1E293B;border-radius:6px;height:12px;overflow:hidden">
    <div style="background:{col};width:{pct:.1f}%;height:100%;border-radius:6px"></div>
  </div>
  <span style="width:110px;font-size:12px;font-weight:700;text-align:right">
    {count} / {n_total}
    <span style="color:#475569;font-weight:400"> ({pct:.0f}%)</span>
  </span>
</div>"""
    return f"""
<div class="block">
  <h2>Query Distribution by Intent</h2>
  <p style="font-size:12px;color:#475569;margin-bottom:16px">
    How all {n_total} scored queries are split across intent categories.
  </p>
  {rows}
</div>"""

# ── Single query card ──────────────────────────────────────────────────────────
def _qcard(entry, idx, our_brand, competitors, all_brands, bg=None):
    q       = entry.get("query","")
    cons    = entry.get("consistency","")
    intent  = entry.get("intent","informational")
    s1      = entry.get("session1",[]) or []
    s2      = entry.get("session2",[]) or []
    s3      = entry.get("session3",[]) or []
    brands  = entry.get("brands",{})
    others  = entry.get("others",[])
    row_bg  = bg or ("var(--bg-card)" if idx%2==0 else "#0A0F1E")

    vis = ""
    for b in all_brands:
        bd      = brands.get(b,{})
        n       = bd.get("sessions_appeared",0)
        col     = "#6366F1" if b == our_brand else "#F59E0B"
        scored  = bd.get("appeared",False)
        tick    = ('<span style="color:#10B981;font-weight:700">✓ point</span>'
                   if scored else
                   '<span style="color:#EF4444">✗ no point</span>')
        vis += (f'<span style="margin-right:16px;font-size:11px;white-space:nowrap">'
                f'<b style="color:{col}">{b}</b> '
                f'<span style="font-weight:700">{n}/3</span> — {tick}</span>')

    others_row = ""
    if others:
        o_dots = " ".join(_dot(o.get("brand",""),"#475569") for o in others[:5])
        others_row = (f'<div style="margin-top:8px;padding-top:8px;'
                      f'border-top:1px dashed var(--border);font-size:11px;color:#475569">'
                      f'<span style="font-weight:700;margin-right:6px">Others visible:</span>'
                      f'{o_dots}</div>')

    return f"""
<div style="background:{row_bg};border:1px solid var(--border);border-radius:10px;
            padding:14px 16px;margin-bottom:10px">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;
              gap:10px;margin-bottom:12px">
    <div style="flex:1">
      {_ibadge(intent)}{_cbadge(cons)}
      <div style="font-size:13px;font-weight:500;margin-top:5px;line-height:1.5">{q}</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:12px">
    <div>
      <div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;
                  letter-spacing:.06em;margin-bottom:5px">Session 1</div>
      <div style="min-height:26px">{_render_session(s1,our_brand,competitors)}</div>
    </div>
    <div>
      <div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;
                  letter-spacing:.06em;margin-bottom:5px">Session 2</div>
      <div style="min-height:26px">{_render_session(s2,our_brand,competitors)}</div>
    </div>
    <div>
      <div style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;
                  letter-spacing:.06em;margin-bottom:5px">Session 3</div>
      <div style="min-height:26px">{_render_session(s3,our_brand,competitors)}</div>
    </div>
  </div>
  <div style="background:#0F172A;border-radius:7px;padding:8px 12px;
              display:flex;flex-wrap:wrap;align-items:center;border:1px solid var(--border)">
    <span style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;
                 letter-spacing:.05em;margin-right:10px">Visibility:</span>
    {vis}
  </div>
  {others_row}
</div>"""

# ── BLOCK 4: Queries grouped by intent ────────────────────────────────────────
def _block_queries(parsed, our_brand, competitors, all_brands):
    scored = [r for r in parsed if _is_scored(r, all_brands)]
    sections = ""
    intent_bg = {"informational":"#6366F106","features":"#10B98106","comparison":"#F59E0B06"}

    for intent, col in INTENT_COLORS.items():
        lbl     = INTENT_LABELS.get(intent,intent)
        queries = [r for r in scored if r.get("intent","informational") == intent]
        if not queries: continue
        hc_q = [r for r in queries if r.get("consistency") == "HC"]
        mc_q = [r for r in queries if r.get("consistency") == "MC"]

        hc_html = ""
        if hc_q:
            hc_html = f"""
<div style="margin-bottom:14px">
  <div style="display:inline-block;font-size:11px;font-weight:700;color:#10B981;
              padding:5px 12px;background:#10B98115;border-radius:6px;
              margin-bottom:10px">● High Confidence — {len(hc_q)} queries</div>
  {"".join(_qcard(e,i,our_brand,competitors,all_brands) for i,e in enumerate(hc_q))}
</div>"""

        mc_html = ""
        if mc_q:
            mc_html = f"""
<div style="margin-bottom:6px">
  <div style="display:inline-block;font-size:11px;font-weight:700;color:#F59E0B;
              padding:5px 12px;background:#F59E0B15;border-radius:6px;
              margin-bottom:10px">● Moderate Confidence — {len(mc_q)} queries</div>
  {"".join(_qcard(e,i,our_brand,competitors,all_brands) for i,e in enumerate(mc_q))}
</div>"""

        sections += f"""
<div style="background:{intent_bg.get(intent,'#0F172A')};border:2px solid {col}33;
            border-left:5px solid {col};border-radius:12px;
            padding:20px;margin-bottom:22px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <span style="font-size:20px;font-weight:900;color:{col}">{lbl}</span>
    <span style="font-size:20px;font-weight:900;color:{col}">{len(queries)}</span>
  </div>
  <div style="font-size:12px;color:#94A3B8;margin-bottom:16px">
    HC: {len(hc_q)} &nbsp;·&nbsp; MC: {len(mc_q)} &nbsp;·&nbsp; Total: {len(queries)}
  </div>
  {hc_html}{mc_html}
</div>"""

    return f"""
<div class="block">
  <h2>All Queries — Grouped by Intent &amp; Confidence</h2>
  <p style="font-size:12px;color:#475569;margin-bottom:18px">
    HC (High Confidence) shown first within each intent, then MC (Moderate Confidence).
    Each card shows 3 Gemini sessions and exact brand visibility per session.
  </p>
  {sections}
</div>"""

# ── BLOCK 5: Dropped queries ───────────────────────────────────────────────────
def _block_dropped(parsed, all_brands):
    dropped = [r for r in parsed if not _is_scored(r, all_brands)]
    if not dropped:
        return ""
    items = ""
    for d in dropped[:60]:
        q  = d.get("query","")
        s1 = ", ".join(d.get("session1",[]) or ["—"])
        s2 = ", ".join(d.get("session2",[]) or ["—"])
        s3 = ", ".join(d.get("session3",[]) or ["—"])
        items += f"""
<div style="border:1px solid #EF444422;border-radius:10px;padding:12px 14px;
            margin-bottom:8px;background:#EF444406">
  <div style="font-size:13px;font-weight:500;margin-bottom:8px">
    {_ibadge(d.get("intent","informational"))}{q}
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;
              font-size:11px;color:#94A3B8">
    <div><b style="color:#EF4444">Session 1:</b> {s1}</div>
    <div><b style="color:#EF4444">Session 2:</b> {s2}</div>
    <div><b style="color:#EF4444">Session 3:</b> {s3}</div>
  </div>
</div>"""
    return f"""
<div class="block" style="border-left:5px solid #EF4444">
  <h2>Dropped Queries — Gemini Uncertain
    <span style="font-size:13px;font-weight:400;color:#475569"> — {len(dropped)} queries</span>
  </h2>
  <p style="font-size:12px;color:#94A3B8;margin-bottom:16px">
    None of the tracked brands (your brand or competitors) appeared in 2 or more
    Gemini sessions for these queries. This means Gemini has no settled answer
    for these topics in the context of your tracked brands — a strategic
    opportunity where no brand has yet established AI visibility.
  </p>
  {items}
</div>"""

# ── BLOCK 6: Brand-exclusive queries ──────────────────────────────────────────
def _block_exclusive(parsed, our_brand, competitors):
    scored   = [r for r in parsed if r.get("consistency") != "DROP"]
    sections = ""
    for i, comp in enumerate(competitors):
        comp_col  = brand_color(i+1)
        our_only  = []
        comp_only = []
        both      = []
        neither   = []
        for e in scored:
            oa = e["brands"].get(our_brand, {}).get("appeared", False)
            ca = e["brands"].get(comp,      {}).get("appeared", False)
            if   oa and not ca: our_only.append(e)
            elif ca and not oa: comp_only.append(e)
            elif oa and ca:     both.append(e)
            else:               neither.append(e)

        def _qlist(entries):
            if not entries:
                return "<p style='padding:12px;font-size:12px;color:#475569'>None</p>"
            return "".join(
                f'<div style="padding:8px 12px;border-bottom:1px solid var(--border);font-size:12px">'
                f'{_ibadge(e.get("intent","informational"))}'
                f'<span style="font-weight:500">{e.get("query","")}</span></div>'
                for e in entries[:40])

        sections += f"""
<div style="margin-bottom:20px">
  <div style="font-size:13px;font-weight:700;margin-bottom:10px;color:#94A3B8">
    <span style="color:#6366F1">{our_brand}</span> vs
    <span style="color:{comp_col}">{comp}</span>
    <span style="font-size:12px;font-weight:400;margin-left:8px;color:#475569">
      Both appeared: {len(both)} queries &nbsp;·&nbsp; Neither: {len(neither)} queries
    </span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div style="border:1px solid #6366F133;border-radius:10px;overflow:hidden">
      <div style="background:#6366F115;padding:10px 14px;font-size:12px;font-weight:700;
                  color:#6366F1;border-bottom:1px solid #6366F133">
        Only {our_brand} appeared — {len(our_only)} queries
      </div>
      {_qlist(our_only)}
    </div>
    <div style="border:1px solid {comp_col}33;border-radius:10px;overflow:hidden">
      <div style="background:{comp_col}15;padding:10px 14px;font-size:12px;font-weight:700;
                  color:{comp_col};border-bottom:1px solid {comp_col}33">
        Only {comp} appeared — {len(comp_only)} queries
      </div>
      {_qlist(comp_only)}
    </div>
  </div>
</div>"""

    return f"""
<div class="block">
  <h2>Brand-Exclusive Query Analysis</h2>
  <p style="font-size:12px;color:#94A3B8;margin-bottom:16px">
    Queries where only one brand appeared in Gemini's responses across 2+ sessions.
    Left side = only your brand. Right side = only the competitor.
  </p>
  {sections}
</div>"""

# ── Main ───────────────────────────────────────────────────────────────────────
def generate_html_report():
    print("\n[Phase 12] Generating dashboard...")
    scores = _load("scores.json")
    meta   = _load("meta.json")
    pp     = f"{OUTPUTS_PATH}/parsed_results.json"
    parsed = json.load(open(pp, encoding="utf-8")) if os.path.exists(pp) else []

    brand_name  = meta.get("brand_name","Your Brand")
    competitors = meta.get("competitors",[])
    all_brands  = [brand_name] + competitors
    scored      = [r for r in parsed if _is_scored(r, all_brands)]
    n_total     = len(scored)
    n_dropped   = len(parsed) - n_total
    n_audited   = len(parsed)
    n_generated = meta.get("queries_generated_for_audit", n_audited)

    summary = _exec_summary(scores, meta)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Visibility Audit — {brand_name}</title>
<style>
:root{{--bg:#09090F;--bg-card:#111121;--border:#1A2035;--text:#E2E8F0;--text-secondary:#94A3B8}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);
      font-family:'Inter',system-ui,sans-serif;
      padding:28px;max-width:1280px;margin:0 auto;line-height:1.5}}
h2{{font-size:18px;font-weight:800;margin-bottom:12px}}
.block{{background:var(--bg-card);border:1px solid var(--border);
        border-radius:14px;padding:24px;margin-bottom:20px}}
@media print{{
  :root{{--bg:#fff;--bg-card:#f8fafc;--border:#e2e8f0;--text:#1e293b}}
  body{{background:#fff;color:#000;padding:12px}}
  .block{{break-inside:avoid;border:1px solid #e2e8f0}}
}}
</style>
</head>
<body>

<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
  <div>
    <div style="font-size:28px;font-weight:900;letter-spacing:-.5px">AI Visibility Audit</div>
    <div style="font-size:13px;color:#475569;margin-top:4px">
      {brand_name} &nbsp;·&nbsp; {meta.get("category","")}
      &nbsp;·&nbsp; {n_generated} selected for audit &nbsp;·&nbsp; {n_total} scored &nbsp;·&nbsp; {n_dropped} dropped
    </div>
  </div>
</div>

<div class="block" style="border-left:5px solid #6366F1;margin-bottom:20px">
  <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;
              letter-spacing:.07em;margin-bottom:8px">Executive Summary</div>
  <p style="font-size:14px;line-height:1.8">{summary}</p>
</div>

{_block_brand(meta)}
{_block_scoring(scores, meta, all_brands, n_total, parsed)}
{_visual_analytics(scores, all_brands)}
{_block_flashcards(scores, meta, all_brands, parsed)}
{_intent_dist(parsed, n_total, all_brands)}
{_block_queries(parsed, brand_name, competitors, all_brands)}
{_block_dropped(parsed, all_brands)}
{_block_exclusive(parsed, brand_name, competitors)}

</body>
</html>"""

    out = f"{OUTPUTS_PATH}/report.html"
    os.makedirs(OUTPUTS_PATH, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Report saved → {out}")

if __name__ == "__main__":
    generate_html_report()