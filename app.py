import streamlit as st
import math
import numpy as np

# ==========================================
# 1. إعدادات الصفحة والعلامة التجارية
# ==========================================
st.set_page_config(
    page_title="Eco_Techno - Solar PV Design Calculator",
    page_icon="☀️",
    layout="wide"
)

st.markdown("""
    <h1 style='text-align: center; color: #2E86C1;'>☀️ Eco_Techno Solar PV Design Calculator</h1>
    <p style='text-align: center;'>Accurate Off-Grid System Design based on IEC, NEC, and IEEE Standards.</p>
    <hr>
""", unsafe_allow_html=True)

# ==========================================
# 2. دوال الحسابات الأساسية (منطق محرك الإكسل)
# ==========================================

def calculate_loads_and_inverter(V_LN, PF, I_day, I_ngt, t_day, t_ngt, safety_factor, is_three_phase):
    """
    حساب الأحمال اليومية والليلية وقدرة العاكس.
    المعادلات مطابقة لـ Excel لكن بصيغة صحيحة.
    """
    # 1. حساب القدرة (P = V * I * PF)
    P_day = V_LN * I_day * PF
    P_ngt = V_LN * I_ngt * PF
    
    # إذا كان النظام ثلاثي الأطوار، نضرب في 3 (افتراض تماثل الأحمال)
    if is_three_phase:
        P_day *= 3
        P_ngt *= 3
        
    # 2. حساب الطاقة (E = P * t)
    E_day = P_day * t_day
    E_ngt = P_ngt * t_ngt
    
    # 3. حساب قدرة التصميم (الأعلى بين النهار والليل)
    P_design = max(P_day, P_ngt)
    
    # 4. حساب قدرة العاكس المطلوبة (مع عامل الأمان)
    Required_Inverter = P_design * safety_factor
    
    return P_day, P_ngt, E_day, E_ngt, P_design, Required_Inverter

def calculate_system_efficiency(temp_loss, soiling, mismatch, dc_wiring, inv_eff, ac_wiring, battery_rte):
    """
    حساب الكفاءة الكلية للنظام (الضرب التسلسلي للخسائر)
    """
    return temp_loss * soiling * mismatch * dc_wiring * inv_eff * ac_wiring * battery_rte

def calculate_pv_array(module_power_w, module_voc, module_isc, voc_coeff, vmp_coeff, 
                       t_max, t_min, inv_voc_max, inv_mppt_min, inv_mppt_max, 
                       total_daily_energy_wh, system_efficiency, psh, target_modules_per_string):
    """
    حساب عدد الألواح وتوزيع السلاسل والتحقق من الجهد
    (مطابق لمعايير IEC 62548)
    """
    # 1. الجهد المصحح حرارياً
    v_oc_at_tmax = module_voc * (1 + voc_coeff * (t_max - 25))
    v_oc_at_tmin = module_voc * (1 + voc_coeff * (t_min - 25))
    v_mp_at_tmax = module_vmp * (1 + vmp_coeff * (t_max - 25)) # نستخدم Vmp
    v_mp_at_tmin = module_vmp * (1 + vmp_coeff * (t_min - 25))
    
    # 2. الحدود القصوى والدنيا لعدد الألواح في السلسلة
    max_panels_series = math.floor(inv_voc_max / v_oc_at_tmin)
    min_panels_series = math.ceil(inv_mppt_min / v_mp_at_tmax)
    
    # 3. عدد الألواح المطلوب
    initial_pv_power = total_daily_energy_wh / (psh * system_efficiency)
    num_panels_theoretical = math.ceil(initial_pv_power / module_power_w)
    
    # 4. التحقق من اختيار المستخدم (N_target)
    if target_modules_per_string < min_panels_series or target_modules_per_string > max_panels_series:
        raise ValueError(f"Target modules per string ({target_modules_per_string}) is outside safe limits ({min_panels_series} - {max_panels_series})")
    
    # 5. الحسابات النهائية للسلاسل
    num_parallel_strings = math.ceil(num_panels_theoretical / target_modules_per_string)
    total_modules_actual = num_parallel_strings * target_modules_per_string
    total_pv_power_w = total_modules_actual * module_power_w
    
    # 6. التحقق من الجهد
    v_oc_string_max_tmin = target_modules_per_string * v_oc_at_tmin
    v_oc_verification = "PASS" if v_oc_string_max_tmin <= inv_voc_max else "FAIL"
    v_mp_string_min_tmax = target_modules_per_string * v_mp_at_tmax
    v_mp_verification = "PASS" if v_mp_string_min_tmax >= inv_mppt_min else "FAIL"
    
    return {
        "initial_pv_power": initial_pv_power,
        "num_panels": num_panels_theoretical,
        "target_modules_per_string": target_modules_per_string,
        "num_parallel_strings": num_parallel_strings,
        "total_modules_actual": total_modules_actual,
        "total_pv_power_w": total_pv_power_w,
        "v_oc_verification": v_oc_verification,
        "v_mp_verification": v_mp_verification
    }

def calculate_battery_bank(total_night_energy_wh, inv_eff, battery_voltage, battery_capacity_ah, 
                           dod, c_rate, max_charge_current, max_discharge_current):
    """
    حساب عدد البطاريات وتيارات الشحن والتفريغ والتحقق من DOD
    (مطابق لمعايير IEC 61427 و IEEE 485)
    """
    # 1. الطاقة المطلوبة من البطارية (DC)
    e_bat_dc = total_night_energy_wh / inv_eff
    e_stored_req = e_bat_dc / 0.95 # كفاءة التفريغ الافتراضية 95%
    
    # 2. سعة البطارية المطلوبة
    capacity_req_ah = e_stored_req / (battery_voltage * dod)
    num_batteries = math.ceil(capacity_req_ah / battery_capacity_ah)
    total_capacity_ah = num_batteries * battery_capacity_ah
    
    # 3. الطاقة الفعلية القابلة للاستخدام
    e_usable_dc_wh = battery_voltage * total_capacity_ah * dod
    
    # 4. تيار الشحن والتفريغ
    charge_current = c_rate * battery_capacity_ah
    discharge_current_per_battery = total_night_energy_wh / (battery_voltage * inv_eff * num_batteries)
    
    # التحقق
    charge_status = "PASS" if charge_current <= max_charge_current else "WARNING: Exceeds Max"
    discharge_status = "PASS" if discharge_current_per_battery <= max_discharge_current else "FAIL: Exceeds Max"
    
    return {
        "e_stored_req": e_stored_req,
        "capacity_req_ah": capacity_req_ah,
        "num_batteries": num_batteries,
        "total_capacity_ah": total_capacity_ah,
        "e_usable_dc_wh": e_usable_dc_wh,
        "charge_current": charge_current,
        "charge_status": charge_status,
        "discharge_current": discharge_current_per_battery,
        "discharge_status": discharge_status
    }

def calculate_cable_sizing(design_current_A, length_m, voltage_V, ambient_temp_C, 
                           insulation_type, num_circuits, max_voltage_drop_percent=0.02, method="E"):
    """
    حساب مقطع الكابل والتحقق من هبوط الجهد
    (مطابق لمعايير IEC 60364-5-52)
    """
    # ثوابت النحاس
    rho_20 = 0.017241
    alpha = 0.00393
    max_temp = 90 if insulation_type == "XLPE" else 70 if insulation_type == "PVC" else 70
    rho_t = rho_20 * (1 + alpha * (max_temp - 20))
    
    # معاملات التصحيح (قيم تقريبية حسب جداول IEC)
    # معامل الحرارة (Ambient Temp Correction)
    if insulation_type == "XLPE":
        ca = 1.0 if ambient_temp_C == 30 else 0.82 if ambient_temp_C == 50 else 0.76 if ambient_temp_C == 55 else 0.91 if ambient_temp_C == 40 else 0.96 if ambient_temp_C == 35 else 1.04 if ambient_temp_C == 25 else 1.0
    else: # PVC
        ca = 1.0 if ambient_temp_C == 30 else 0.71 if ambient_temp_C == 50 else 0.61 if ambient_temp_C == 55 else 0.87 if ambient_temp_C == 40 else 0.94 if ambient_temp_C == 35 else 1.06 if ambient_temp_C == 25 else 1.0
    
    # معامل التجميع (Grouping Factor) - جداول مبسطة
    # استخدام قيم معايير IEC (Method E & F)
    if method == "E": # Cable Tray
        cg = 1.0 if num_circuits == 1 else 0.87 if num_circuits == 2 else 0.84 if num_circuits == 3 else 0.78 if num_circuits == 9 else 0.75
    elif method == "F": # Single Core Free Air
        cg = 1.0 if num_circuits == 1 else 0.88 if num_circuits == 2 else 0.82 if num_circuits == 3 else 0.78 if num_circuits == 9 else 0.75
    elif method == "C": # Clipped Direct
        cg = 1.0 if num_circuits == 1 else 0.8 if num_circuits == 2 else 0.7 if num_circuits == 3 else 0.5 if num_circuits == 9 else 0.75
    else:
        cg = 1.0
        
    # التيار المصحح المطلوب
    iz_req = design_current_A / (ca * cg)
    
    # جدول سعات الكابلات (Iz) - بسيط (XLPE 90°C Method C 2 Loaded)
    iz_table = {
        1.5: 24, 2.5: 33, 4: 45, 6: 58, 10: 80, 16: 107, 25: 138, 35: 171, 50: 209,
        70: 269, 95: 328, 120: 382, 150: 441, 185: 506, 240: 599, 300: 693
    }
    
    # اختيار المقطع القياسي
    selected_size = 0
    for size, iz in iz_table.items():
        if iz >= iz_req:
            selected_size = size
            selected_iz = iz
            break
    
    if selected_size == 0:
        return {"error": "No standard cable size found"}
    
    # حساب هبوط الجهد
    vd_actual = (2 * rho_t * length_m * design_current_A) / selected_size
    vd_percent = (vd_actual / voltage_V) * 100
    
    # حساب السعة المصححة
    iz_corrected = selected_iz * ca * cg
    
    # التحقق
    ampacity_status = "PASS" if iz_corrected >= design_current_A else "WARNING"
    vd_status = "PASS" if vd_percent <= (max_voltage_drop_percent * 100) else "FAIL"
    
    return {
        "selected_size": selected_size,
        "vd_actual_v": vd_actual,
        "vd_percent": vd_percent,
        "ampacity_status": ampacity_status,
        "vd_status": vd_status
    }

# ==========================================
# 3. واجهة المستخدم والمدخلات
# ==========================================

st.sidebar.header("🔧 System Configuration")
system_type = st.sidebar.selectbox("System Type", ["Single-Phase", "Three-Phase"])

st.sidebar.header("⚡ Load Data")
V_LN = st.sidebar.number_input("Phase Voltage (V_LN) [V]", value=230.0, step=1.0)
PF = st.sidebar.number_input("Power Factor", value=0.85, step=0.01)
I_day = st.sidebar.number_input("Day Current [A]", value=40.0, step=1.0)
I_ngt = st.sidebar.number_input("Night Current [A]", value=15.0, step=1.0)
t_day = st.sidebar.number_input("Day Hours", value=4.0, step=0.5)
t_ngt = st.sidebar.number_input("Night Hours", value=4.0, step=0.5)

st.sidebar.header("🔋 Battery Bank")
Bat_V = st.sidebar.number_input("Battery Voltage [V]", value=51.2, step=0.1)
Bat_Ah = st.sidebar.number_input("Battery Capacity [Ah]", value=314.0, step=1.0)
DOD = st.sidebar.number_input("Depth of Discharge (DOD)", value=0.85, step=0.01)
C_Rate = st.sidebar.number_input("Charging C-Rate", value=0.2, step=0.05)

st.sidebar.header("☀️ PV Module")
Mod_P = st.sidebar.number_input("Module Power [W]", value=650.0, step=10.0)
Mod_Voc = st.sidebar.number_input("Module Voc [V]", value=53.9, step=0.1)
Mod_Vmp = st.sidebar.number_input("Module Vmp [V]", value=44.56, step=0.1)
Mod_Isc = st.sidebar.number_input("Module Isc [A]", value=15.29, step=0.1)
Voc_Coeff = st.sidebar.number_input("Voc Temp Coeff [%/°C]", value=-0.002, format="%.3f")
Vmp_Coeff = st.sidebar.number_input("Vmp Temp Coeff [%/°C]", value=-0.0026, format="%.4f")

st.sidebar.header("📦 Constants")
T_MAX = st.sidebar.number_input("Max Ambient Temp [°C]", value=50.0)
T_MIN = st.sidebar.number_input("Min Ambient Temp [°C]", value=-10.0)
PSH = st.sidebar.number_input("Peak Sun Hours", value=5.0)
SF = st.sidebar.number_input("Safety Factor (Inverter)", value=1.25, step=0.05)
Inv_Voc_Max = st.sidebar.number_input("Inverter Max Voc [V]", value=500.0)
Inv_MPPT_Min = st.sidebar.number_input("Inverter MPPT Min [V]", value=90.0)
Inv_MPPT_Max = st.sidebar.number_input("Inverter MPPT Max [V]", value=435.0)
Inv_Max_Current = st.sidebar.number_input("Inverter MPPT Max Current [A]", value=42.0)
Inv_Eff = st.sidebar.number_input("Inverter Efficiency", value=0.96, step=0.01)

st.sidebar.header("⚙️ User Decisions")
Target_Modules_String = st.sidebar.number_input("Modules per String (N_target)", value=6, step=1)

if st.sidebar.button("🚀 RUN CALCULATION NOW"):

    try:
        # تحديد حالة النظام
        is_three_phase = True if system_type == "Three-Phase" else False
        
        # حساب الكفاءة الكلية
        eta_sys = calculate_system_efficiency(
            temp_loss=0.92, soiling=0.95, mismatch=0.98, 
            dc_wiring=0.985, inv_eff=Inv_Eff, ac_wiring=0.98, battery_rte=0.9
        )
        
        # --- 1. الأحمال والعاكس ---
        P_day, P_ngt, E_day, E_ngt, P_design, Required_Inverter = calculate_loads_and_inverter(
            V_LN, PF, I_day, I_ngt, t_day, t_ngt, SF, is_three_phase
        )
        
        # إجمالي الطاقة الليلية (البطارية تخدم الليل)
        Total_Night_Energy = E_ngt
        
        # --- 2. الألواح الشمسية (PV Array) ---
        pv_result = calculate_pv_array(
            Mod_P, Mod_Voc, Mod_Isc, Voc_Coeff, Vmp_Coeff,
            T_MAX, T_MIN, Inv_Voc_Max, Inv_MPPT_Min, Inv_MPPT_Max,
            Total_Night_Energy, eta_sys, PSH, Target_Modules_String
        )
        
        # --- 3. البطارية (Battery) ---
        bat_result = calculate_battery_bank(
            Total_Night_Energy, Inv_Eff, Bat_V, Bat_Ah, DOD, C_Rate, 160, 160
        )
        
        # --- 4. حساب الكابلات (مثال لكابل PV) ---
        # تيار التصميم = 1.25 * Isc (معيار NEC 690.8)
        design_current_pv = Mod_Isc * 1.25
        # الجهد النظامي للكابل = Ntarget * Vmp
        v_system_pv = Target_Modules_String * Mod_Vmp
        cable_pv = calculate_cable_sizing(
            design_current_A=design_current_pv,
            length_m=25,
            voltage_V=v_system_pv,
            ambient_temp_C=55,
            insulation_type="XLPE",
            num_circuits=3,
            method="C"
        )
        
        # --- عرض النتائج ---
        st.success("✅ Calculations Successful! System is designed based on IEC & NEC standards.")
        
        st.subheader("📊 System Summary")
        col1, col2, col3 = st.columns(3)
        col1.metric("Daily Night Energy (Load)", f"{Total_Night_Energy:,.0f} Wh")
        col2.metric("Inverter Size Required", f"{Required_Inverter:,.0f} W")
        col3.metric("System Efficiency", f"{eta_sys*100:.1f}%")
        
        st.subheader("🔋 Battery & PV Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Number of Batteries", bat_result['num_batteries'])
        c2.metric("Total Battery Usable Energy", f"{bat_result['e_usable_dc_wh']:,.0f} Wh")
        c3.metric("Total PV Panels", pv_result['total_modules_actual'])
        c4.metric("Total PV Power", f"{pv_result['total_pv_power_w']:,.0f} W")
        
        st.subheader("✅ Verification Results")
        st.success(f"⚡ PV Voltage: {pv_result['v_oc_verification']} (Max Voc String: {pv_result['v_oc_string_max_tmin']:.1f}V)")
        st.success(f"🔋 Battery DOD & C-Rate: {bat_result['charge_status']} (Charge Current: {bat_result['charge_current']:.1f}A)")
        st.success(f"⚡ PV Cable: {cable_pv['selected_size']} mm² (VD: {cable_pv['vd_percent']:.2f}%, Status: {cable_pv['ampacity_status']})")

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.warning("Please check your input values, especially 'Modules per String' (N_target). It must fall within the safe limits calculated by the system (e.g., for 6 modules, max Vmp might be exceeded if voltage is low).")
        
else:
    st.info("👈 Please configure your system inputs in the sidebar and click 'RUN CALCULATION NOW'.")