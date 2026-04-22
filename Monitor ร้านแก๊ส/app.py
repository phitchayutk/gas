import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import io

st.set_page_config(
    page_title="Gas Sales Monitor",
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

# ─── Default Embedded Data ────────────────────────────────────────────────────
DEFAULT_DATA = {
    "month": [3,4,5,6,7,8,9,10,11,12]*3,
    "market": ["ตลาด 1"]*10 + ["ตลาด 2"]*10 + ["ตลาด 3"]*10,
    "kg4":  [95,113,199,166,202,196,127,155,181,157,
             252,257,324,274,330,308,369,310,167,140,
             306,295,314,283,300,299,357,392,371,361],
    "kg7":  [83,89,92,86,117,101,86,107,225,240,
             269,266,297,266,310,275,300,304,210,195,
             208,178,193,159,191,170,188,186,175,189],
    "kg15": [767,865,905,833,1120,1064,785,921,1123,1064,
             1229,1128,1394,1162,1227,1023,1265,1035,739,798,
             1178,1100,1109,1142,1189,978,1124,1122,1144,1071],
    "kg48": [29,16,42,3,7,43,2,40,63,117,
             125,106,141,109,111,107,128,124,139,101,
             0,19,0,10,8,0,23,15,29,20],
}

MONTH_TH = {
    1:"ม.ค.",2:"ก.พ.",3:"มี.ค.",4:"เม.ย.",5:"พ.ค.",6:"มิ.ย.",
    7:"ก.ค.",8:"ส.ค.",9:"ก.ย.",10:"ต.ค.",11:"พ.ย.",12:"ธ.ค."
}

# ─── Excel Parser ─────────────────────────────────────────────────────────────
def _safe_num(val) -> float:
    try:
        v = float(val)
        return 0.0 if np.isnan(v) else v
    except Exception:
        return 0.0


def _parse_pivot_format(file_bytes: bytes) -> pd.DataFrame:
    """
    Parse Pivot Table format (ต้นฉบับ):
      Row 0: unit header
      Row 1: column labels
      Data:  ยอดขาย ตลาด X → month number → date rows
    """
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None)

    # หา header row
    header_row = None
    for i, row in raw.iterrows():
        row_str = " ".join(str(v) for v in row.values).lower()
        if "row labels" in row_str or "sum of" in row_str:
            header_row = i
            break
    if header_row is None:
        raise ValueError("ไม่พบ header ใน Pivot format (ต้องมี 'Row Labels' หรือ 'Sum of')")

    data_raw = raw.iloc[header_row + 1:].reset_index(drop=True)
    # col positions: 0=label, 1=kg4, 2=kg7, 3=kg15, 4=kg15_buy, 5=kg48
    size_col_map = {"kg4": 1, "kg7": 2, "kg15": 3, "kg48": 5}

    records = []
    current_market = None
    current_month = None

    for _, row in data_raw.iterrows():
        label = str(row.iloc[0]).strip()
        if label in ("", "nan", "(blank)", "Grand Total"):
            continue
        if "ยอดขาย ตลาด" in label:
            current_market = label.replace("ยอดขาย ", "").strip()
            current_month = None
            continue
        if "หน้าร้าน" in label:
            current_market = None
            continue
        if label.isdigit() and 1 <= int(label) <= 12:
            current_month = int(label)
            if current_market:
                try:
                    records.append({
                        "market": current_market,
                        "month":  current_month,
                        "kg4":   _safe_num(row.iloc[size_col_map["kg4"]]),
                        "kg7":   _safe_num(row.iloc[size_col_map["kg7"]]),
                        "kg15":  _safe_num(row.iloc[size_col_map["kg15"]]),
                        "kg48":  _safe_num(row.iloc[size_col_map["kg48"]]),
                    })
                except Exception:
                    pass
            continue

    if not records:
        raise ValueError("ไม่พบข้อมูลตลาดในไฟล์ กรุณาตรวจสอบ format")

    result = pd.DataFrame(records)
    result["month_name"] = result["month"].map(MONTH_TH)
    return result


def _parse_flat_format(file_bytes: bytes) -> pd.DataFrame:
    """
    Flat format: columns date | market | kg4 | kg7 | kg15 | kg48
    หรือ Long:   columns date | market | size | quantity
    """
    df = pd.read_excel(io.BytesIO(file_bytes))
    df.columns = [str(c).strip().lower().replace(" ", "").replace("_", "") for c in df.columns]

    col_map = {}
    for c in df.columns:
        if any(k in c for k in ["date","วันที่","วัน"]):
            col_map[c] = "date"
        elif any(k in c for k in ["market","ตลาด","สาขา"]):
            col_map[c] = "market"
        elif "4" in c and "kg" in c:
            col_map[c] = "kg4"
        elif "7" in c and "kg" in c:
            col_map[c] = "kg7"
        elif "15" in c and "kg" in c:
            col_map[c] = "kg15"
        elif "48" in c and "kg" in c:
            col_map[c] = "kg48"
        elif any(k in c for k in ["size","ขนาด"]):
            col_map[c] = "size"
        elif any(k in c for k in ["qty","quantity","จำนวน","ยอด"]):
            col_map[c] = "quantity"
    df = df.rename(columns=col_map)

    if "date" not in df.columns:
        raise ValueError("ไม่พบคอลัมน์วันที่ (date / วันที่)")
    if "market" not in df.columns:
        raise ValueError("ไม่พบคอลัมน์ตลาด (market / ตลาด)")

    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["date"])
    df["month"] = df["date"].dt.month

    if "size" in df.columns and "quantity" in df.columns:
        df["size_num"] = df["size"].astype(str).str.extract(r"(\d+)").astype(float)
        df["size_col"] = "kg" + df["size_num"].astype(int).astype(str)
        df = df.pivot_table(
            index=["month", "market"], columns="size_col",
            values="quantity", aggfunc="sum"
        ).reset_index()
        df.columns.name = None

    for col in ["kg4", "kg7", "kg15", "kg48"]:
        if col not in df.columns:
            df[col] = 0

    result = df.groupby(["month", "market"])[["kg4", "kg7", "kg15", "kg48"]].sum().reset_index()
    result["month_name"] = result["month"].map(MONTH_TH)
    return result


def parse_excel(file) -> tuple:
    file_bytes = file.read()
    raw = pd.read_excel(io.BytesIO(file_bytes), header=None)
    head_str = raw.iloc[:5].to_string().lower()

    if "unit" in head_str or "ถัง" in head_str or "row labels" in head_str:
        return _parse_pivot_format(file_bytes), "Pivot (ต้นฉบับ)"
    return _parse_flat_format(file_bytes), "Flat / Long format"


# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⛽ Gas Sales Monitor")
    st.caption("ระบบติดตามยอดขายก๊าซหุงต้ม")
    st.divider()

    st.markdown("### 📂 อัปโหลดข้อมูล Excel")
    st.markdown('<div class="upload-box">', unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "ลาก Excel มาวางที่นี่ (.xlsx / .xls)",
        type=["xlsx", "xls"],
        label_visibility="collapsed"
    )

    with st.expander("📋 Format ที่รองรับ"):
        st.markdown("""
**Format 1 — Pivot (ต้นฉบับ)**
Pivot Table เหมือนไฟล์ที่ให้มา มี:
- `ยอดขาย ตลาด 1`, `ยอดขาย ตลาด 2` ...
- Row month เป็นตัวเลข 3–12

**Format 2 — Flat รายวัน**
| date | market | kg4 | kg7 | kg15 | kg48 |
|---|---|---|---|---|---|
| 1/3/2568 | ตลาด 1 | 5 | 3 | 44 | 0 |

**Format 3 — Long format**
| date | market | size | quantity |
|---|---|---|---|
| 1/3/2568 | ตลาด 1 | 15 kg | 44 |
        """)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Load data ──
    parse_error = None
    data_source = "🗃️ ข้อมูลตัวอย่าง (Embedded)"

    if uploaded is not None:
        try:
            df_uploaded, fmt = parse_excel(uploaded)
            df = df_uploaded
            data_source = f"📄 {uploaded.name} ({fmt})"
            st.success(f"✅ โหลดสำเร็จ — {len(df)} แถว / {df['market'].nunique()} ตลาด")
        except Exception as e:
            parse_error = str(e)
            df = pd.DataFrame(DEFAULT_DATA)
            df["month_name"] = df["month"].map(MONTH_TH)
            st.error(f"❌ {parse_error}")
    else:
        df = pd.DataFrame(DEFAULT_DATA)
        df["month_name"] = df["month"].map(MONTH_TH)

    st.divider()

    # ── Filters ──
    all_markets = sorted(df["market"].unique().tolist())
    selected_markets = st.multiselect("เลือกตลาด", options=all_markets, default=all_markets)

    selected_size = st.selectbox(
        "ขนาดถัง (Primary KPI)",
        options=["kg15", "kg4", "kg7", "kg48"],
        format_func=lambda x: {"kg15":"15 kg","kg4":"4 kg","kg7":"7 kg","kg48":"48 kg"}[x]
    )
    size_label = {"kg15":"15 kg","kg4":"4 kg","kg7":"7 kg","kg48":"48 kg"}[selected_size]

    all_months = sorted(df["month"].unique().tolist())
    month_min, month_max = int(min(all_months)), int(max(all_months))
    selected_months = st.slider(
        "ช่วงเดือน",
        min_value=month_min, max_value=month_max,
        value=(month_min, month_max)
    )

    st.divider()
    st.caption(f"📌 {data_source}")

# ─── Filter ───────────────────────────────────────────────────────────────────
dff = df[
    df["market"].isin(selected_markets) &
    df["month"].between(selected_months[0], selected_months[1])
].copy()

if dff.empty:
    st.warning("ไม่พบข้อมูลตามเงื่อนไขที่เลือก กรุณาเปลี่ยนตัวกรอง")
    st.stop()

# ─── Source Badge ─────────────────────────────────────────────────────────────
badge_text = "📄 ข้อมูลจากไฟล์ที่อัปโหลด" if (uploaded and not parse_error) else "🗃️ ข้อมูลตัวอย่าง Embedded"
st.markdown(
    f'<span class="source-badge" style="background:rgba(88,166,255,0.12);'
    f'color:#58a6ff;border:1px solid rgba(88,166,255,0.3);">{badge_text}</span>',
    unsafe_allow_html=True
)

# ─── KPI Cards ────────────────────────────────────────────────────────────────
st.markdown("### 📊 ภาพรวมยอดขาย")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(f"รวม ถัง {size_label}", f"{int(dff[selected_size].sum()):,}")
col2.metric("ถัง 15 kg", f"{int(dff['kg15'].sum()):,}")
col3.metric("ถัง 4 kg",  f"{int(dff['kg4'].sum()):,}")
col4.metric("ถัง 7 kg",  f"{int(dff['kg7'].sum()):,}")
col5.metric("ถัง 48 kg", f"{int(dff['kg48'].sum()):,}")

st.divider()

# ─── Color Map ────────────────────────────────────────────────────────────────
palette = ["#58a6ff","#3fb950","#f78166","#ffa657","#d2a8ff"]
color_map = {m: palette[i % len(palette)] for i, m in enumerate(sorted(df["market"].unique()))}

# ─── Row 1: Trend + Pie ───────────────────────────────────────────────────────
col_a, col_b = st.columns([3, 1])

with col_a:
    st.markdown(f"#### 📈 แนวโน้มรายเดือน — ถัง {size_label}")
    monthly_by_market = (
        dff.groupby(["month","month_name","market"])[selected_size]
        .sum().reset_index().sort_values("month")
    )
    fig_trend = px.line(
        monthly_by_market, x="month_name", y=selected_size, color="market",
        markers=True, color_discrete_map=color_map, template="plotly_dark",
        labels={selected_size:"จำนวน (ถัง)","month_name":"เดือน","market":"ตลาด"}
    )
    fig_trend.update_traces(line_width=2.5, marker_size=7)
    fig_trend.update_layout(
        height=300, margin=dict(l=0,r=0,t=10,b=0),
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

with col_b:
    st.markdown("#### 🥧 สัดส่วนตลาด")
    pie_data = dff.groupby("market")[selected_size].sum().reset_index()
    fig_pie = px.pie(
        pie_data, values=selected_size, names="market",
        color="market", color_discrete_map=color_map,
        template="plotly_dark", hole=0.45
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    fig_pie.update_layout(
        height=300, margin=dict(l=0,r=0,t=10,b=0), showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ─── Row 2: Stacked + Grouped ─────────────────────────────────────────────────
col_c, col_d = st.columns(2)

with col_c:
    st.markdown("#### 📦 ยอดขายทุกขนาดถัง (Stacked)")
    all_sizes = (
        dff.groupby(["month","month_name"])[["kg4","kg7","kg15","kg48"]]
        .sum().reset_index().sort_values("month")
    )
    size_colors = {"kg4":"#d2a8ff","kg7":"#ffa657","kg15":"#58a6ff","kg48":"#3fb950"}
    size_names  = {"kg4":"4 kg","kg7":"7 kg","kg15":"15 kg","kg48":"48 kg"}
    fig_bar = go.Figure()
    for sz in ["kg48","kg15","kg7","kg4"]:
        fig_bar.add_trace(go.Bar(
            name=size_names[sz], x=all_sizes["month_name"], y=all_sizes[sz],
            marker_color=size_colors[sz]
        ))
    fig_bar.update_layout(
        barmode="stack", height=280, margin=dict(l=0,r=0,t=10,b=0),
        template="plotly_dark",
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        yaxis_title="จำนวน (ถัง)"
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_d:
    st.markdown(f"#### 🏪 เปรียบเทียบตลาด — {size_label}")
    market_month = (
        dff.groupby(["market","month_name","month"])[selected_size]
        .sum().reset_index().sort_values("month")
    )
    fig_mbar = px.bar(
        market_month, x="month_name", y=selected_size,
        color="market", barmode="group", color_discrete_map=color_map,
        template="plotly_dark",
        labels={selected_size:"จำนวน (ถัง)","month_name":"เดือน","market":"ตลาด"}
    )
    fig_mbar.update_layout(
        height=280, margin=dict(l=0,r=0,t=10,b=0),
        legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="left",x=0),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_mbar, use_container_width=True)

# ─── Weekly Heatmap ───────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 🗓️ Weekly Schedule Heatmap — คาดการณ์ยอดรายวัน")

day_weights = {
    "จันทร์":1.05,"อังคาร":0.98,"พุธ":1.10,
    "พฤหัส":1.02,"ศุกร์":1.08,"เสาร์":0.85,"อาทิตย์":0.75
}
day_order = ["จันทร์","อังคาร","พุธ","พฤหัส","ศุกร์","เสาร์","อาทิตย์"]

monthly_total = (
    dff.groupby(["month","month_name"])[selected_size]
    .sum().reset_index().sort_values("month")
)
heat_data = {}
for _, row in monthly_total.iterrows():
    per_day = row[selected_size] / 26
    heat_data[row["month_name"]] = {d: round(per_day * w) for d, w in day_weights.items()}

heat_df = pd.DataFrame(heat_data, index=day_order)
fig_heat = px.imshow(
    heat_df, labels=dict(x="เดือน",y="วัน",color="ถัง"),
    color_continuous_scale="Blues", aspect="auto",
    template="plotly_dark", text_auto=True
)
fig_heat.update_layout(
    height=280, margin=dict(l=0,r=0,t=10,b=0),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
)
fig_heat.update_traces(textfont_size=11)
st.plotly_chart(fig_heat, use_container_width=True)

# ─── Order Schedule ───────────────────────────────────────────────────────────
st.divider()
st.markdown("#### 📋 แนะนำวันสั่งซื้อ (Order Schedule)")

monthly_avg = dff.groupby("month")[selected_size].sum().mean()
thr_high = monthly_avg / 4 * 1.15
thr_low  = monthly_avg / 4 * 0.85

schedule_rows = []
for mname, mdata in heat_df.items():
    for day, val in mdata.items():
        if val >= thr_high:
            level, action = "🔴 สูง", "สั่งล่วงหน้า 2 วัน"
        elif val >= thr_low:
            level, action = "🟡 ปกติ", "สั่งตามแผน"
        else:
            level, action = "🟢 ต่ำ", "ลดสต็อก"
        schedule_rows.append({
            "เดือน": mname, "วัน": day,
            "คาดการณ์ (ถัง)": val, "ระดับ": level, "แนะนำ": action
        })

schedule_df = pd.DataFrame(schedule_rows)
pivot = schedule_df.pivot_table(
    index="วัน", columns="เดือน", values="คาดการณ์ (ถัง)", aggfunc="first"
).reindex(day_order)
month_order = [MONTH_TH[m] for m in sorted(dff["month"].unique())]
pivot = pivot[[c for c in month_order if c in pivot.columns]]

st.dataframe(
    pivot.style.background_gradient(cmap="Blues", axis=None),
    use_container_width=True, height=290
)

col_e, col_f = st.columns(2)
with col_e:
    st.markdown("**📌 วันที่ควรสั่งมากที่สุด (Top 3)**")
    for i, (day, val) in enumerate(heat_df.mean(axis=1).sort_values(ascending=False).head(3).items()):
        st.markdown(f"**{i+1}. {day}** — เฉลี่ย `{val:.0f}` ถัง/วัน")

with col_f:
    st.markdown("**📌 เดือนที่ยอดสูงสุด (Top 3)**")
    top_months = (
        dff.groupby(["month","month_name"])[selected_size]
        .sum().reset_index().sort_values(selected_size, ascending=False).head(3)
    )
    for _, row in top_months.iterrows():
        st.markdown(f"**{row['month_name']}** — `{int(row[selected_size]):,}` ถัง")

# ─── Raw Data Preview ─────────────────────────────────────────────────────────
with st.expander("🔍 ดูข้อมูลดิบ (Raw Data)"):
    st.dataframe(dff.sort_values(["market","month"]), use_container_width=True)
    csv = dff.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "⬇️ ดาวน์โหลด CSV",
        data=csv.encode("utf-8-sig"),
        file_name="gas_sales_filtered.csv",
        mime="text/csv"
    )

# ─── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption("⛽ Gas Sales Monitor · Streamlit + Plotly · รองรับ Excel Upload (Pivot / Flat / Long format)")
