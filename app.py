import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import io

st.set_page_config(
    page_title="Gas Sales Monitor — LIG",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }
    .upload-box {
        border: 1.5px dashed rgba(88,166,255,0.4);
        border-radius: 10px;
        padding: 1rem 1.25rem;
        background: rgba(88,166,255,0.04);
        margin-bottom: 0.5rem;
    }
    .source-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

MONTH_TH = {
    1:"ม.ค.",2:"ก.พ.",3:"มี.ค.",4:"เม.ย.",5:"พ.ค.",6:"มิ.ย.",
    7:"ก.ค.",8:"ส.ค.",9:"ก.ย.",10:"ต.ค.",11:"พ.ย.",12:"ธ.ค."
}

# ─── DEFAULT DATA (จากไฟล์จริง ร้านแก๊ส by day) ────────────────────────────
DEFAULT_DATA = {
    "month":  [3,4,5,6,7,8,9,10,11,12, 3,4,5,6,7,8,9,10,11,12, 3,4,5,6,7,8,9,10,11,12],
    "market": (["ตลาด 1"]*10) + (["ตลาด 2"]*10) + (["ตลาด 3"]*10),
    "kg4":  [ 95,113,199,166,202,196,127,155,181,157,
             252,257,324,274,330,308,369,310,167,140,
             306,295,314,283,300,299,357,392,371,361],
    "kg7":  [ 83, 89, 92, 86,117,101, 86,107,225,240,
             269,266,297,266,310,275,300,304,210,195,
             208,178,193,159,191,170,188,186,175,189],
    "kg15": [ 767, 865, 905, 833,1120,1064, 785, 921,1123,1064,
             1229,1128,1394,1162,1227,1023,1265,1035, 739, 798,
             1174,1100,1101,1133,1189, 978,1124,1122,1144,1071],
    "kg48": [ 29, 16, 42,  3,  7, 43,  2, 40, 63,117,
             125,106,141,109,111,107,128,124,139,101,
               0, 19,  0, 10,  8,  0, 23, 15, 29, 20],
}

# ─── Helpers ──────────────────────────────────────────────────────────────────
def _safe_num(val) -> float:
    try:
        v = float(val)
        return 0.0 if np.isnan(v) else v
    except Exception:
        return 0.0

def _thai_date_to_gregorian(s):
    s = str(s).strip()
    if not s or ":" in s or s in ("nan",""):
        return None
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        if y > 2400: y -= 543
        if 1900 <= y <= 2100:
            return pd.Timestamp(year=y, month=m, day=d)
    except Exception:
        pass
    return None

# ─── CSV Pivot-LIG Parser ─────────────────────────────────────────────────────
def _parse_pivot_csv(file_bytes: bytes) -> pd.DataFrame:
    """
    Parse CSV export จาก Excel Pivot ของ LIG:
      Row 0: unit :???,4,7,15,48
      Row 1: Row Labels,Sum of Unit 4 kg,...
      Data:  ?????? ???? 1  (ตลาด 1 — Thai encoding เสีย)
             3              (เดือน)
             3/3/2568,...   (รายวัน)
    """
    text = file_bytes.decode("utf-8", errors="replace")
    lines = [l.strip() for l in text.splitlines()]

    def safe_int(v):
        try: return int(float(v))
        except: return 0

    def parse_date(s):
        s = s.strip()
        if not s or ":" in s: return None
        parts = s.split("/")
        if len(parts) != 3: return None
        try:
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y > 2400: y -= 543
            if 1900 <= y <= 2100: return (y, m, d)
        except Exception:
            pass
        return None

    records = []
    current_market = None
    current_month  = None
    market_num     = 0

    for line in lines[2:]:
        if not line: continue
        parts = [p.strip() for p in line.split(",")]
        label = parts[0]
        if not label or label in ("Grand Total", "(blank)"): continue

        # Market detection: "?????? ???? N" (ตลาด) vs "????????" (หน้าร้าน)
        if "?????" in label:
            # หน้าร้านมี ? ล้วนๆ ไม่มีช่องว่างหรือตัวเลขตามหลัง
            stripped = label.replace("?", "").replace(" ", "")
            if stripped.isdigit() or stripped == "":
                if " " not in label.strip("?"):
                    current_market = None   # หน้าร้าน — หยุด
                    continue
            market_num    += 1
            current_market = f"ตลาด {market_num}"
            current_month  = None
            continue

        if label.isdigit() and 1 <= int(label) <= 12:
            current_month = int(label)
            continue

        if current_market and current_month:
            date = parse_date(label)
            if date:
                records.append({
                    "market": current_market,
                    "month":  current_month,
                    "kg4":  safe_int(parts[1]) if len(parts) > 1 else 0,
                    "kg7":  safe_int(parts[2]) if len(parts) > 2 else 0,
                    "kg15": safe_int(parts[3]) if len(parts) > 3 else 0,
                    "kg48": safe_int(parts[4]) if len(parts) > 4 else 0,
                })

    if not records:
        raise ValueError("ไม่พบข้อมูลในไฟล์ CSV — ตรวจสอบ format")

    df = pd.DataFrame(records)
    agg = df.groupby(["month","market"])[["kg4","kg7","kg15","kg48"]].sum().reset_index()
    agg["month_name"] = agg["month"].map(MONTH_TH)
    return agg

def _parse_csv_flat(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if any(k in cl for k in ["date","วันที่"]):    col_map[c] = "date"
        elif any(k in cl for k in ["market","ตลาด"]):  col_map[c] = "market"
        elif "4"  in cl: col_map[c] = "kg4"
        elif "7"  in cl: col_map[c] = "kg7"
        elif "15" in cl: col_map[c] = "kg15"
        elif "48" in cl: col_map[c] = "kg48"
    df = df.rename(columns=col_map)
    if "date" not in df.columns:
        raise ValueError("ไม่พบคอลัมน์ date")
    df["date"]  = df["date"].astype(str).apply(_thai_date_to_gregorian)
    df = df.dropna(subset=["date"])
    df["month"] = df["date"].apply(lambda d: d.month)
    if "market" not in df.columns:
        df["market"] = "ตลาดรวม"
    for col in ["kg4","kg7","kg15","kg48"]:
        if col not in df.columns: df[col] = 0
    agg = df.groupby(["month","market"])[["kg4","kg7","kg15","kg48"]].sum().reset_index()
    agg["month_name"] = agg["month"].map(MONTH_TH)
    return agg

def parse_csv(file) -> tuple:
    file_bytes = file.read()
    preview    = file_bytes[:600].decode("utf-8", errors="replace")
    lines      = preview.split("\n")
    row0 = lines[0].lower() if lines else ""
    row1 = lines[1].lower() if len(lines) > 1 else ""
    if "unit" in row0 or "row labels" in row1:
        return _parse_pivot_csv(file_bytes), "CSV Pivot (LIG format)"
    return _parse_csv_flat(file_bytes), "CSV Flat"

# ─── Excel Parsers ────────────────────────────────────────────────────────────
def _parse_pivot_excel(file_bytes: bytes) -> pd.DataFrame:
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
    header_row = None
    for i, row in raw.iterrows():
        row_str = " ".join(str(v) for v in row.values).lower()
        if "row labels" in row_str or "sum of" in row_str:
            header_row = i
            break
    if header_row is None:
        raise ValueError("ไม่พบ header ใน Pivot Excel")
    data_raw = raw.iloc[header_row + 1:].reset_index(drop=True)
    size_col_map = {"kg4":1,"kg7":2,"kg15":3,"kg48":5}
    records = []
    current_market = None
    for _, row in data_raw.iterrows():
        label = str(row.iloc[0]).strip()
        if label in ("","nan","(blank)","Grand Total"): continue
        if "ยอดขาย ตลาด" in label:
            current_market = label.replace("ยอดขาย ","").strip()
            continue
        if "หน้าร้าน" in label:
            current_market = None
            continue
        if label.isdigit() and 1 <= int(label) <= 12 and current_market:
            try:
                records.append({
                    "market": current_market,
                    "month":  int(label),
                    "kg4":  _safe_num(row.iloc[size_col_map["kg4"]]),
                    "kg7":  _safe_num(row.iloc[size_col_map["kg7"]]),
                    "kg15": _safe_num(row.iloc[size_col_map["kg15"]]),
                    "kg48": _safe_num(row.iloc[size_col_map["kg48"]]),
                })
            except Exception:
                pass
    if not records:
        raise ValueError("ไม่พบข้อมูลตลาดใน Excel")
    result = pd.DataFrame(records)
    result["month_name"] = result["month"].map(MONTH_TH)
    return result

def _parse_flat_excel(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(c).strip().lower().replace(" ","") for c in df.columns]
    col_map = {}
    for c in df.columns:
        if any(k in c for k in ["date","วันที่"]):    col_map[c] = "date"
        elif any(k in c for k in ["market","ตลาด"]):  col_map[c] = "market"
        elif "4kg"  in c or c == "4": col_map[c] = "kg4"
        elif "7kg"  in c or c == "7": col_map[c] = "kg7"
        elif "15kg" in c or c == "15": col_map[c] = "kg15"
        elif "48kg" in c or c == "48": col_map[c] = "kg48"
    df = df.rename(columns=col_map)
    df["date"]  = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"])
    df["month"] = df["date"].dt.month
    if "market" not in df.columns: df["market"] = "ตลาดรวม"
    for col in ["kg4","kg7","kg15","kg48"]:
        if col not in df.columns: df[col] = 0
    result = df.groupby(["month","market"])[["kg4","kg7","kg15","kg48"]].sum().reset_index()
    result["month_name"] = result["month"].map(MONTH_TH)
    return result

def parse_excel(file) -> tuple:
    file_bytes = file.read()
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
    head_str = raw.iloc[:5].to_string().lower()
    if "row labels" in head_str or "sum of" in head_str or "unit" in head_str:
        return _parse_pivot_excel(file_bytes), "Excel Pivot"
    return _parse_flat_excel(file_bytes), "Excel Flat"

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⛽ Gas Sales Monitor")
    st.caption("บริษัท ลพบุรี อุตสาหกรรมแก๊ส จำกัด (LIG)")
    st.divider()

    st.markdown("### 📂 อัปโหลดข้อมูลใหม่")
    st.markdown('<div class="upload-box">', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "ลาก CSV หรือ Excel มาวางที่นี่",
        type=["csv","xlsx","xls"],
        label_visibility="collapsed"
    )
    with st.expander("📋 Format ที่รองรับ"):
        st.markdown("""
**✅ CSV Pivot (LIG ต้นฉบับ)**
Export จาก Excel Pivot ตรงๆ ได้เลย
```
unit :???,4,7,15,48
Row Labels,...
?????? ???? 1,...
3,...
3/3/2568,3,7,65,0
```
**✅ CSV Flat**
```
date,market,kg4,kg7,kg15,kg48
3/3/2568,ตลาด 1,3,7,65,0
```
**✅ Excel Pivot / Flat** (รองรับเช่นกัน)

*วันที่รองรับทั้ง พ.ศ. และ ค.ศ.*
        """)
    st.markdown('</div>', unsafe_allow_html=True)

    parse_error = None
    data_source = "📦 ข้อมูล LIG จริง (Embedded จากไฟล์ต้นฉบับ)"

    if uploaded is not None:
        try:
            fname = uploaded.name.lower()
            if fname.endswith(".csv"):
                df_up, fmt = parse_csv(uploaded)
            else:
                df_up, fmt = parse_excel(uploaded)
            df = df_up
            data_source = f"📄 {uploaded.name} ({fmt})"
            st.success(f"✅ โหลดสำเร็จ — {df['market'].nunique()} ตลาด, {len(df)} แถว")
        except Exception as e:
            parse_error = str(e)
            df = pd.DataFrame(DEFAULT_DATA)
            df["month_name"] = df["month"].map(MONTH_TH)
            st.error(f"❌ {parse_error}")
    else:
        df = pd.DataFrame(DEFAULT_DATA)
        df["month_name"] = df["month"].map(MONTH_TH)

    st.divider()

    all_markets = sorted(df["market"].unique().tolist())
    selected_markets = st.multiselect("เลือกตลาด", options=all_markets, default=all_markets)

    selected_size = st.selectbox(
        "ขนาดถัง (Primary KPI)",
        options=["kg15","kg4","kg7","kg48"],
        format_func=lambda x: {"kg15":"15 kg","kg4":"4 kg","kg7":"7 kg","kg48":"48 kg"}[x]
    )
    size_label = {"kg15":"15 kg","kg4":"4 kg","kg7":"7 kg","kg48":"48 kg"}[selected_size]

    all_months = sorted(df["month"].unique().tolist())
    selected_months = st.slider(
        "ช่วงเดือน",
        min_value=int(min(all_months)), max_value=int(max(all_months)),
        value=(int(min(all_months)), int(max(all_months)))
    )

    st.divider()
    st.markdown("### 🔄 Before / After")
    improve_month = st.number_input(
        "เดือนที่เริ่ม Improve (เม.ย. = 4)",
        min_value=1, max_value=12, value=4
    )
    st.divider()
    st.caption(f"📌 {data_source}")

# ─── Filter ───────────────────────────────────────────────────────────────────
dff = df[
    df["market"].isin(selected_markets) &
    df["month"].between(selected_months[0], selected_months[1])
].copy()

if dff.empty:
    st.warning("ไม่พบข้อมูล กรุณาเปลี่ยนตัวกรอง")
    st.stop()

# ─── Source Badge ─────────────────────────────────────────────────────────────
badge_color = "rgba(63,185,80,0.15)" if (uploaded and not parse_error) else "rgba(88,166,255,0.12)"
badge_text  = f"📄 {uploaded.name}" if (uploaded and not parse_error) else "📦 ข้อมูล LIG ต้นฉบับ (Embedded)"
st.markdown(
    f'<span class="source-badge" style="background:{badge_color};'
    f'color:#58a6ff;border:1px solid rgba(88,166,255,0.3);">{badge_text}</span>',
    unsafe_allow_html=True
)

# ─── KPI Cards ────────────────────────────────────────────────────────────────
st.markdown("### 📊 ภาพรวมยอดขาย")
c1,c2,c3,c4,c5 = st.columns(5)
c1.metric(f"รวม {size_label}", f"{int(dff[selected_size].sum()):,} ถัง")
c2.metric("15 kg", f"{int(dff['kg15'].sum()):,}")
c3.metric("4 kg",  f"{int(dff['kg4'].sum()):,}")
c4.metric("7 kg",  f"{int(dff['kg7'].sum()):,}")
c5.metric("48 kg", f"{int(dff['kg48'].sum()):,}")
st.divider()

# ─── Color Map ────────────────────────────────────────────────────────────────
palette   = ["#58a6ff","#3fb950","#f78166","#ffa657","#d2a8ff"]
color_map = {m: palette[i % len(palette)] for i, m in enumerate(sorted(df["market"].unique()))}

# ─── Row 1: Trend + Pie ───────────────────────────────────────────────────────
col_a, col_b = st.columns([3,1])
with col_a:
    st.markdown(f"#### 📈 แนวโน้มรายเดือน — {size_label}")
    mtm = dff.groupby(["month","month_name","market"])[selected_size].sum().reset_index().sort_values("month")
    fig = px.line(mtm, x="month_name", y=selected_size, color="market",
                  markers=True, color_discrete_map=color_map, template="plotly_dark",
                  labels={selected_size:"จำนวน (ถัง)","month_name":"เดือน","market":"ตลาด"})
    fig.update_traces(line_width=2.5, marker_size=7)
    fig.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                      legend=dict(orientation="h",y=1.08,x=0),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)

with col_b:
    st.markdown("#### 🥧 สัดส่วนตลาด")
    pie = dff.groupby("market")[selected_size].sum().reset_index()
    fig2 = px.pie(pie, values=selected_size, names="market",
                  color="market", color_discrete_map=color_map,
                  template="plotly_dark", hole=0.45)
    fig2.update_traces(textposition="inside", textinfo="percent+label")
    fig2.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0), showlegend=False,
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig2, use_container_width=True)

# ─── Row 2: Stacked + Grouped ─────────────────────────────────────────────────
col_c, col_d = st.columns(2)
with col_c:
    st.markdown("#### 📦 ยอดขายทุกขนาดถัง (Stacked)")
    sz_all = dff.groupby(["month","month_name"])[["kg4","kg7","kg15","kg48"]].sum().reset_index().sort_values("month")
    sz_colors = {"kg4":"#d2a8ff","kg7":"#ffa657","kg15":"#58a6ff","kg48":"#3fb950"}
    sz_names  = {"kg4":"4 kg","kg7":"7 kg","kg15":"15 kg","kg48":"48 kg"}
    fig3 = go.Figure()
    for sz in ["kg48","kg15","kg7","kg4"]:
        fig3.add_trace(go.Bar(name=sz_names[sz], x=sz_all["month_name"], y=sz_all[sz],
                              marker_color=sz_colors[sz]))
    fig3.update_layout(barmode="stack", height=280, margin=dict(l=0,r=0,t=10,b=0),
                       template="plotly_dark",
                       legend=dict(orientation="h",y=1.08,x=0),
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       yaxis_title="จำนวน (ถัง)")
    st.plotly_chart(fig3, use_container_width=True)

with col_d:
    st.markdown(f"#### 🏪 เปรียบเทียบตลาด — {size_label}")
    mm = dff.groupby(["market","month_name","month"])[selected_size].sum().reset_index().sort_values("month")
    fig4 = px.bar(mm, x="month_name", y=selected_size, color="market",
                  barmode="group", color_discrete_map=color_map, template="plotly_dark",
                  labels={selected_size:"จำนวน (ถัง)","month_name":"เดือน","market":"ตลาด"})
    fig4.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                       legend=dict(orientation="h",y=1.08,x=0),
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig4, use_container_width=True)

# ─── Before / After ───────────────────────────────────────────────────────────
st.divider()
before_lbl = f"Before (ก่อน {MONTH_TH.get(improve_month,'?')})"
after_lbl  = f"After ({MONTH_TH.get(improve_month,'?')}–ปัจจุบัน)"

dff["period"] = dff["month"].apply(lambda m: after_lbl if m >= improve_month else before_lbl)
ba = dff.groupby(["period","market"])[selected_size].mean().reset_index().rename(columns={selected_size:"avg"})

st.markdown(f"#### 🔄 Before vs After — จุดเริ่ม Improve: **{MONTH_TH.get(improve_month,'?')}** (เดือน {improve_month})")

bdf = ba[ba["period"] == before_lbl]
adf = ba[ba["period"] == after_lbl]
if not bdf.empty and not adf.empty:
    cols = st.columns(len(selected_markets))
    for i, mkt in enumerate(sorted(selected_markets)):
        bv = bdf[bdf["market"]==mkt]["avg"].values
        av = adf[adf["market"]==mkt]["avg"].values
        if len(bv)>0 and len(av)>0:
            delta = (av[0]-bv[0])/bv[0]*100 if bv[0]>0 else 0
            cols[i].metric(mkt, f"{av[0]:.0f} ถัง/เดือน", f"{delta:+.1f}% vs before")

fig5 = px.bar(ba, x="market", y="avg", color="period", barmode="group",
              template="plotly_dark",
              color_discrete_map={before_lbl:"#f78166", after_lbl:"#3fb950"},
              labels={"avg":f"เฉลี่ย {size_label} (ถัง/เดือน)","market":"ตลาด","period":"ช่วง"})
fig5.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                   legend=dict(orientation="h",y=1.08,x=0),
                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
st.plotly_chart(fig5, use_container_width=True)

# ─── Weekly Heatmap ───────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 🗓️ คาดการณ์ยอดรายวัน (Weekly Heatmap)")
day_weights = {"จันทร์":1.05,"อังคาร":0.98,"พุธ":1.10,"พฤหัส":1.02,"ศุกร์":1.08,"เสาร์":0.85,"อาทิตย์":0.75}
day_order   = list(day_weights.keys())
monthly_total = dff.groupby(["month","month_name"])[selected_size].sum().reset_index().sort_values("month")
heat_data = {}
for _, row in monthly_total.iterrows():
    ppd = row[selected_size] / 26
    heat_data[row["month_name"]] = {d: round(ppd * w) for d, w in day_weights.items()}
heat_df = pd.DataFrame(heat_data, index=day_order)
fig6 = px.imshow(heat_df, labels=dict(x="เดือน",y="วัน",color="ถัง"),
                 color_continuous_scale="Blues", aspect="auto",
                 template="plotly_dark", text_auto=True)
fig6.update_layout(height=270, margin=dict(l=0,r=0,t=10,b=0),
                   plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
fig6.update_traces(textfont_size=11)
st.plotly_chart(fig6, use_container_width=True)

# ─── Order Schedule ───────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 📋 แนะนำวันสั่งซื้อ (Order Schedule)")
avg_mo = dff.groupby("month")[selected_size].sum().mean()
thr_hi = avg_mo / 4 * 1.15
thr_lo = avg_mo / 4 * 0.85
sched_rows = []
for mn, md in heat_df.items():
    for day, val in md.items():
        lvl = "🔴 สูง" if val >= thr_hi else ("🟡 ปกติ" if val >= thr_lo else "🟢 ต่ำ")
        act = "สั่งล่วงหน้า 2 วัน" if val >= thr_hi else ("สั่งตามแผน" if val >= thr_lo else "ลดสต็อก")
        sched_rows.append({"เดือน":mn,"วัน":day,"คาดการณ์ (ถัง)":val,"ระดับ":lvl,"แนะนำ":act})
sched_df = pd.DataFrame(sched_rows)
pivot_s  = sched_df.pivot_table(index="วัน", columns="เดือน", values="คาดการณ์ (ถัง)", aggfunc="first").reindex(day_order)
mo_order = [MONTH_TH[m] for m in sorted(dff["month"].unique())]
pivot_s  = pivot_s[[c for c in mo_order if c in pivot_s.columns]]
st.dataframe(pivot_s.style.background_gradient(cmap="Blues", axis=None), use_container_width=True, height=290)

col_e, col_f = st.columns(2)
with col_e:
    st.markdown("**📌 วันที่ยอดสูงสุด (Top 3)**")
    for i,(day,val) in enumerate(heat_df.mean(axis=1).sort_values(ascending=False).head(3).items()):
        st.markdown(f"**{i+1}. {day}** — เฉลี่ย `{val:.0f}` ถัง/วัน")
with col_f:
    st.markdown("**📌 เดือนที่ยอดสูงสุด (Top 3)**")
    top_mo = dff.groupby(["month","month_name"])[selected_size].sum().reset_index().sort_values(selected_size, ascending=False).head(3)
    for _, row in top_mo.iterrows():
        st.markdown(f"**{row['month_name']}** — `{int(row[selected_size]):,}` ถัง")

# ─── Raw Data ─────────────────────────────────────────────────────────────────
with st.expander("🔍 ดูข้อมูลดิบ (Raw Data)"):
    st.dataframe(dff.sort_values(["market","month"]), use_container_width=True)
    st.download_button("⬇️ ดาวน์โหลด CSV",
                       data=dff.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                       file_name="lig_sales_filtered.csv", mime="text/csv")

st.divider()
st.caption("⛽ Gas Sales Monitor · LIG · Streamlit + Plotly · รองรับ CSV Pivot / Flat + Excel · วันที่ พ.ศ./ค.ศ.")
