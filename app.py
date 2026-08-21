import streamlit as st
import solar_engine

# ==========================================
# 1. PAGE CONFIGURATION (Branding for your Channel)
# ==========================================
st.set_page_config(
    page_title="Eco_Techno Solar PV Calculator",
    page_icon="☀️",
    layout="wide"
)

st.markdown("""
    <h1 style='text-align: center; color: #2E86C1;'>☀️ Eco_Techno Solar PV Design Calculator</h1>
    <p style='text-align: center;'>Accurate Off-Grid System Design based on IEC, NEC, and IEEE Standards.</p>
    <hr>
""", unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR: USER INPUTS (Excel Yellow Cells)
# ==========================================
st.sidebar.header("1. 📊 Load Data")
V_LN = st.sidebar.number_input("Phase Voltage (VLN) [V]", value=230.0, step=1.0)
PF = st.sidebar.number_input("Power Factor (PF)", value=0.85, step=0.01)

col1, col2 = st.sidebar.columns(2)
I_day = col1.number_input("Day Current [A]", value=40.0, step=1.0)
I_ngt = col2.number_input("Night Current [A]", value=15.0, step=1.0)
T_day = col1.number_input("Day Hours", value=4.0, step=0.5)
T_ngt = col2.number_input("Night Hours", value=4.0, step=0.5)

st.sidebar.header("2. 🔋 Battery Data")
Bat_V = st.sidebar.number_input("Battery Voltage [V]", value=51.2, step=0.1)
Bat_Ah = st.sidebar.number_input("Battery Capacity [Ah]", value=314.0, step=1.0)
DOD = st.sidebar.number_input("Depth of Discharge (DOD)", value=0.85, step=0.01)
C_Rate = st.sidebar.number_input("C-Rate", value=0.2, step=0.05)

st.sidebar.header("3. ☀️ PV Module Data")
Mod_P = st.sidebar.number_input("Module Power [W]", value=650.0, step=10.0)
Mod_Voc = st.sidebar.number_input("Module Voc [V]", value=53.9, step=0.1)
Mod_Isc = st.sidebar.number_input("Module Isc [A]", value=15.29, step=0.1)
Voc_Coeff = st.sidebar.number_input("Temp Coeff Voc [%/°C]", value=-0.002, format="%.3f")
Vmp_Coeff = st.sidebar.number_input("Temp Coeff Vmp [%/°C]", value=-0.0026, format="%.4f")

if st.sidebar.button("🔎 RUN CALCULATION NOW"):
    
    # --- CONSTANTS FROM YOUR EXCEL ---
    SAFETY_FACTOR = 1.25
    INV_EFF = 0.96
    T_MAX = 50
    T_MIN = -10
    PSH = 5.0 # Peak Sun Hours
    INV_VOC_MAX = 750
    INV_MPPT_MIN = 450
    
    # --- STEP 1: LOADS & INVERTER ---
    load_results = solar_engine.calculate_loads_and_inverter(
        V_LN, PF, I_day, I_day, I_day, I_ngt, I_ngt, I_ngt, T_day, T_ngt, SAFETY_FACTOR
    )
    
    # --- STEP 2: SYSTEM EFFICIENCY ---
    eta_sys = solar_engine.calculate_system_efficiency(inv_efficiency=INV_EFF)
    
    # --- STEP 3: PV ARRAY ---
    pv_results = solar_engine.calculate_pv_array(
        Mod_P, Mod_Voc, Mod_Isc, Voc_Coeff, 
        T_MAX, T_MIN, INV_VOC_MAX, INV_MPPT_MIN, 500, # Inv MPPT Max assumed 500
        load_results["Total_Night_Energy_Wh"], eta_sys, PSH, 6
    )
    
    # --- STEP 4: BATTERY BANK ---
    bat_results = solar_engine.calculate_battery_bank(
        load_results["Total_Night_Energy_Wh"], INV_EFF, 
        Bat_V, Bat_Ah, DOD, C_Rate, 160, 160 # Max Charge/Discharge set to 160A (from your Excel)
    )
    
    # --- STEP 5: CABLE SIZING (PV Example) ---
    cable_results = solar_engine.calculate_dc_cable(
        design_current_A=Mod_Isc * 1.25,
        length_m=30,
        system_voltage_V=Mod_Voc * pv_results["target_modules_per_string"],
        ambient_temp_C=55,
        insulation_type="XLPE",
        num_circuits=9
    )
    
    # ==========================================
    # 3. DASHBOARD: DISPLAY RESULTS (Excel Green Cells)
    # ==========================================
    st.header("📊 Calculation Results & Verification")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Night Energy (Load)", f"{load_results['Total_Night_Energy_Wh']:,.0f} Wh")
    col2.metric("System Efficiency", f"{eta_sys * 100:.1f}%")
    col3.metric("Inverter Required Power", f"{load_results['Single_Phase_Inverter_Rating']:,.0f} W")
    
    st.subheader("🔋 Battery & PV Array Details")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Batteries Required", bat_results['num_batteries'])
    c2.metric("Total Usable Energy (DC)", f"{bat_results['e_usable_dc_wh']:,.0f} Wh")
    c3.metric("Total PV Panels", pv_results['total_modules_actual'])
    c4.metric("Total PV Power", f"{pv_results['total_pv_power_w']:,.0f} W")
    
    st.subheader("✅ System Verifications")
    st.success(f"⚡ Inverter Voltage Check: {pv_results['v_oc_verification']} (Voc max: {pv_results['v_oc_string_max_tmin']:.1f}V vs Limit {INV_VOC_MAX}V)")
    st.success(f"🔋 Battery Check: {bat_results['charge_status']} (Current: {bat_results['design_charge_current']:.1f}A)")
    
    st.subheader("⚡ PV Cable Sizing Verification (IEC 60364-5-52)")
    st.write(f"**Selected Cable:** {cable_results['selected_mm2']} mm²")
    st.write(f"**Ampacity Check:** {cable_results['ampacity_verification']} (Iz_corrected: {cable_results['Iz_corrected']:.1f}A >= Design Current)")
    st.write(f"**Voltage Drop:** {cable_results['vd_percent']:.2f}% - {cable_results['vd_verification']}")
    
    st.markdown("---")
    st.markdown("""
    *Disclaimer: This tool provides calculated guidelines based on IEC, NEC, and IEEE standards. 
    Final designs must be validated by a certified professional engineer prior to installation.*
    """)

else:
    st.info("👈 Please fill in the input parameters in the sidebar and click 'RUN CALCULATION NOW'.")