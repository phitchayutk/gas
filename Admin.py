import streamlit as st
import pandas as pd
import io
from utils.auth import login_form, logout
from utils.inventory import deploy_device, receive_device, swap_device, bulk_import, edit_device, delete_device
from utils.sheets import load_inventory, save_inventory, append_audit

st.set_page_config(page_title="Admin", page_icon="⚙️", layout="wide")
st.title("⚙️ Admin Panel")

# ─── Auth ──────────────────────────────────────────────────────────────────────
is_admin = login_form()
if not is_admin:
    st.warning("🔐 กรุณา Login เพื่อเข้าใช้งาน Admin Panel")
    st.stop()

admin_name = st.session_state.get("admin_name", "Admin")
st.success(f"🔓 เข้าสู่ระบบในฐานะ: {admin_name}")
if st.button("🚪 Logout"):
    logout()
    st.rerun()

st.markdown("---")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🚀 Deploy", "📥 Receive", "🔄 Swap", "➕ Add Manual", "📤 Import Excel", "✏️ Edit / Delete"
])

# ── Tab 1: Deploy ──────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### 🚀 นำอุปกรณ์ออกใช้งาน")
    st.info("เปลี่ยน Status จาก Available → Disable และบันทึก Location / Ticket")

    d_sn       = st.text_input("Serial Number (SN) *", placeholder="เช่น CAT1940V0NM", key="d_sn")
    d_location = st.text_input("Location ปลายทาง *", placeholder="เช่น nrt_trg_lpe1", key="d_loc")
    d_ticket   = st.text_input("Case Ticket", placeholder="เช่น 2332", key="d_ticket")

    if st.button("🚀 Deploy", key="btn_deploy"):
        if not d_sn or not d_location:
            st.error("กรุณากรอก SN และ Location")
        else:
            ok, msg = deploy_device(d_sn, d_location, d_ticket, admin_name)
            st.success(msg) if ok else st.error(msg)

# ── Tab 2: Receive ─────────────────────────────────────────────────────────────
with tab2:
    st.markdown("### 📥 นำอุปกรณ์เข้าระบบ")
    st.info("เพิ่มอุปกรณ์ใหม่เข้า Inventory พร้อม Status Available")

    df_now    = load_inventory()
    pid_list  = sorted(df_now["PID"].dropna().unique().tolist()) if not df_now.empty else []
    pid_list  = pid_list + ["อื่นๆ (พิมพ์เอง)"]

    r_pid_sel  = st.selectbox("PID *", pid_list, key="r_pid_sel")
    r_pid_text = st.text_input("PID (พิมพ์เอง)", placeholder="เช่น ASR-920-24SZ-IM V01", key="r_pid_text")
    r_sn       = st.text_input("Serial Number (SN) *", placeholder="เช่น CAT1941V17T", key="r_sn")
    r_source   = st.text_input("ได้รับมาจาก", placeholder="เช่น pkn_bso_lpe1", key="r_source")
    r_location = st.text_input("Location เริ่มต้น", placeholder="เช่น SC-SRT", key="r_location")
    r_remark   = st.text_input("Remark", key="r_remark")

    if st.button("📥 รับเข้าระบบ", key="btn_receive"):
        pid_final = r_pid_text if r_pid_sel == "อื่นๆ (พิมพ์เอง)" else r_pid_sel
        if not pid_final or not r_sn:
            st.error("กรุณากรอก PID และ SN")
        else:
            ok, msg = receive_device(pid_final, r_sn, r_source, r_location, r_remark, admin_name)
            st.success(msg) if ok else st.error(msg)

# ── Tab 3: Swap ────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### 🔄 เปลี่ยนอุปกรณ์ (Swap)")
    st.info("Deploy ตัวใหม่ออกไป + รับตัวเสียกลับเข้า Inventory")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**ตัวใหม่ที่ Deploy ออกไป**")
        s_new_sn   = st.text_input("SN ตัวใหม่ *", placeholder="เช่น CAT1940V0NM", key="s_new_sn")
        s_location = st.text_input("Location *", placeholder="เช่น nrt_trg_lpe1", key="s_loc")
        s_ticket   = st.text_input("Case Ticket", placeholder="เช่น 2332", key="s_ticket")
    with col2:
        st.markdown("**ตัวเสียที่รับกลับมา**")
        s_faulty_sn = st.text_input("SN ตัวเสีย *", placeholder="เช่น CAT1940V0D2", key="s_faulty_sn")
        s_faulty_code = st.text_input("Faulty Code", placeholder="เช่น CAT2438U09F", key="s_faulty_code")

    if st.button("🔄 Swap", key="btn_swap"):
        if not s_new_sn or not s_faulty_sn or not s_location:
            st.error("กรุณากรอกข้อมูลที่จำเป็น (*)")
        else:
            ok, msg = swap_device(s_new_sn, s_faulty_sn, s_location, s_ticket, s_faulty_code, admin_name)
            st.success(msg) if ok else st.error(msg)

# ── Tab 4: Add Manual ──────────────────────────────────────────────────────────
with tab4:
    st.markdown("### ➕ Add อุปกรณ์ Manual")

    col1, col2 = st.columns(2)
    with col1:
        m_pid      = st.text_input("PID *", placeholder="เช่น ASR-920-12SZ-D V01", key="m_pid")
        m_sn       = st.text_input("SN *", placeholder="เช่น CAT2346U35F", key="m_sn")
        m_source   = st.text_input("ได้รับมาจาก", key="m_source")
        m_status   = st.selectbox("Status", ["Available", "Disable", "Faulty"], key="m_status")
    with col2:
        m_location = st.text_input("Location", key="m_location")
        m_ticket   = st.text_input("Case Ticket", key="m_ticket")
        m_faulty   = st.text_input("Faulty Code", key="m_faulty")
        m_remark   = st.text_input("Remark", key="m_remark")

    if st.button("➕ เพิ่มอุปกรณ์", key="btn_manual"):
        if not m_pid or not m_sn:
            st.error("กรุณากรอก PID และ SN")
        else:
            df_c = load_inventory()
            if m_sn.strip().upper() in df_c["SN"].str.upper().values:
                st.error(f"SN {m_sn} มีอยู่ในระบบแล้ว")
            else:
                new_row = {
                    "No": str(len(df_c)+1), "PID": m_pid, "SN": m_sn,
                    "ได้รับมาจาก": m_source, "Status": m_status,
                    "Location": m_location, "Case Ticket": m_ticket,
                    "Faulty": m_faulty, "Remark": m_remark
                }
                df_c = pd.concat([df_c, pd.DataFrame([new_row])], ignore_index=True)
                save_inventory(df_c)
                append_audit("ManualAdd", m_sn, m_pid, f"เพิ่มด้วย Manual | Status: {m_status}", admin_name)
                st.success(f"✅ เพิ่ม {m_sn} สำเร็จ")

# ── Tab 5: Import Excel ────────────────────────────────────────────────────────
with tab5:
    st.markdown("### 📤 Import จาก Excel")

    template_cols = ["PID","SN","ได้รับมาจาก","Status","Location","Case Ticket","Faulty","Remark"]
    sample = [
        ["ASR-920-12SZ-D V01","CAT2332U3A0","pbi_nyp_lpe1","Disable","ssk_whn_lpe1","2309","CAT2438U09F","ของเสียคืนแล้ว"],
        ["ASR-920-24SZ-IM V01","CAT1938V0NM","acr_cnm_lpe1","Available","SC-SRT","","",""],
    ]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame(sample, columns=template_cols).to_excel(w, index=False, sheet_name="inventory")
    st.download_button("⬇️ Download Excel Template", buf.getvalue(),
                       "inventory_template.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")
    uploaded = st.file_uploader("อัปโหลดไฟล์ Excel (.xlsx)", type=["xlsx"], key="excel_upload")
    if uploaded:
        preview = pd.read_excel(uploaded)
        st.markdown("**Preview (5 rows แรก):**")
        st.dataframe(preview.head(5), use_container_width=True)
        if st.button("✅ ยืนยัน Import", key="btn_import"):
            uploaded.seek(0)
            ok, msg = bulk_import(uploaded, admin_name)
            st.success(msg) if ok else st.error(msg)

# ── Tab 6: Edit / Delete ───────────────────────────────────────────────────────
with tab6:
    st.markdown("### ✏️ แก้ไข / ลบอุปกรณ์")
    sn_edit = st.text_input("ใส่ SN ที่ต้องการแก้ไข", key="edit_sn")

    if sn_edit:
        df_e = load_inventory()
        row  = df_e[df_e["SN"].str.upper() == sn_edit.strip().upper()]
        if row.empty:
            st.error(f"ไม่พบ SN: {sn_edit}")
        else:
            r = row.iloc[0]
            col1, col2 = st.columns(2)
            status_opts = ["Available", "Disable", "Faulty"]
            cur_status  = r["Status"] if r["Status"] in status_opts else "Available"
            with col1:
                e_status   = st.selectbox("Status", status_opts, index=status_opts.index(cur_status), key="e_status")
                e_location = st.text_input("Location", value=str(r["Location"]), key="e_location")
                e_ticket   = st.text_input("Case Ticket", value=str(r["Case Ticket"]), key="e_ticket")
            with col2:
                e_faulty   = st.text_input("Faulty Code", value=str(r["Faulty"]), key="e_faulty")
                e_source   = st.text_input("ได้รับมาจาก", value=str(r["ได้รับมาจาก"]), key="e_source")
                e_remark   = st.text_input("Remark", value=str(r["Remark"]), key="e_remark")

            col_s, col_d = st.columns(2)
            with col_s:
                if st.button("💾 บันทึก", key="btn_save"):
                    updates = {"Status": e_status, "Location": e_location,
                               "Case Ticket": e_ticket, "Faulty": e_faulty,
                               "ได้รับมาจาก": e_source, "Remark": e_remark}
                    ok, msg = edit_device(sn_edit, updates, admin_name)
                    st.success(msg) if ok else st.error(msg)
            with col_d:
                if st.button("🗑️ ลบ", key="btn_delete"):
                    ok, msg = delete_device(sn_edit, admin_name)
                    st.success(msg) if ok else st.error(msg)
