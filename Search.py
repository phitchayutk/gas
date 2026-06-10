import streamlit as st
import pandas as pd
from utils.sheets import load_inventory
import io

st.set_page_config(page_title="Search", page_icon="🔍", layout="wide")
st.title("🔍 ค้นหาอุปกรณ์")

with st.spinner("กำลังโหลดข้อมูล..."):
    df = load_inventory()

if df.empty:
    st.warning("ยังไม่มีข้อมูลในระบบ")
    st.stop()

# ─── Search bar หลัก ──────────────────────────────────────────────────────────
st.markdown("### 🔎 ค้นหา")
col_s, col_f = st.columns([3, 1])
with col_s:
    keyword = st.text_input(
        "พิมพ์คำค้นหา",
        placeholder="พิมพ์อะไรก็ได้ เช่น SN / PID / Location / Status / Remark / Case Ticket...",
        label_visibility="collapsed"
    )
with col_f:
    status_filter = st.selectbox("Status", ["ทั้งหมด", "Available", "Disable", "Faulty"],
                                  label_visibility="collapsed")

# ─── Filter ───────────────────────────────────────────────────────────────────
filtered = df.copy()

# Status filter
if status_filter != "ทั้งหมด":
    filtered = filtered[filtered["Status"] == status_filter]

# Keyword: ค้นหาทุก column ใน row
if keyword.strip():
    kw = keyword.strip().upper()
    mask = filtered.apply(
        lambda row: row.astype(str).str.upper().str.contains(kw, na=False).any(),
        axis=1
    )
    filtered = filtered[mask]

# ─── Results ──────────────────────────────────────────────────────────────────
st.markdown(f"### ผลการค้นหา ({len(filtered)} รายการ)")

if filtered.empty:
    st.info("ไม่พบข้อมูลที่ค้นหา")
else:
    def highlight_status(row):
        if row["Status"] == "Available":
            return ["background-color: #d4edda"] * len(row)
        elif row["Status"] == "Disable":
            return ["background-color: #f8d7da"] * len(row)
        elif row["Status"] == "Faulty":
            return ["background-color: #fff3cd"] * len(row)
        return [""] * len(row)

    inv_cols = ["No", "PID", "SN", "ได้รับมาจาก", "Status", "Location", "Case Ticket", "Faulty", "Remark"]
    st.dataframe(
        filtered.style.apply(highlight_status, axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={c: st.column_config.TextColumn(c) for c in inv_cols}
    )

    # ─── Export ───────────────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        csv = filtered.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Export CSV", csv, "search_result.csv", "text/csv")
    with col2:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            filtered.to_excel(writer, index=False, sheet_name="SearchResult")
        st.download_button("⬇️ Export Excel", buf.getvalue(), "search_result.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ─── SN Detail ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### 📋 ดูรายละเอียด SN")
sn_detail = st.text_input("ใส่ SN เพื่อดูข้อมูลและประวัติ", key="sn_detail")
if sn_detail:
    row = df[df["SN"].str.upper() == sn_detail.strip().upper()]
    if row.empty:
        st.error(f"ไม่พบ SN: {sn_detail}")
    else:
        r = row.iloc[0]
        status_icon = {"Available": "✅", "Disable": "🔴", "Faulty": "⚠️"}.get(r["Status"], "❓")
        st.markdown(f"""
        | Field | Value |
        |---|---|
        | **PID** | {r['PID']} |
        | **SN** | {r['SN']} |
        | **Status** | {status_icon} {r['Status']} |
        | **Location** | {r['Location']} |
        | **ได้รับมาจาก** | {r['ได้รับมาจาก']} |
        | **Case Ticket** | {r['Case Ticket']} |
        | **Faulty Code** | {r['Faulty']} |
        | **Remark** | {r['Remark']} |
        """)
