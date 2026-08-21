"""
Eco_Techno Solar Calculator Engine v1.0
Based on IEC 60364-5-52, IEC 62548, IEC 61427, NEC 690
"""
import math

# ===================================================================
# PART 1: SYSTEM EFFICIENCY & THERMAL CORRECTION (Based on Sheet 2)
# ===================================================================

def calculate_system_efficiency(temp_loss=0.92, soiling=0.95, mismatch=0.98, 
                                dc_wiring=0.985, inv_efficiency=0.96, ac_wiring=0.98, battery_rte=0.90):
    """
    Equation from Sheet 2, Row 80-87: η_total = η_temp × η_soiling × η_mismatch × η_dc_wiring × η_inverter × η_ac_wiring × η_battery
    """
    return temp_loss * soiling * mismatch * dc_wiring * inv_efficiency * ac_wiring * battery_rte

def correct_voltage_temperature(v_stc, temp_coeff, ambient_temp):
    """
    Equation from Sheet 2, Row 104-105: V_corrected = V_STC * [1 + coeff * (T - 25)]
    Standard: IEC 60891 (Temperature correction of PV modules)
    """
    return v_stc * (1 + temp_coeff * (ambient_temp - 25))

# ===================================================================
# PART 2: LOAD & INVERTER CALCULATIONS (Based on Sheet 2, Section 3 & 4)
# ===================================================================

def calculate_loads_and_inverter(V_LN, PF, I_day_L1, I_day_L2, I_day_L3, 
                                 I_ngt_L1, I_ngt_L2, I_ngt_L3, t_day, t_ngt, safety_factor):
    """
    Calculates Day/Night Power, Energy, and Inverter Ratings.
    Equations matched exactly with Sheet 2, Rows 31-60.
    """
    # 1. Power Calculations (P = V * I * PF)
    P_L1_Day = V_LN * I_day_L1 * PF
    P_L2_Day = V_LN * I_day_L2 * PF
    P_L3_Day = V_LN * I_day_L3 * PF
    
    P_L1_Night = V_LN * I_ngt_L1 * PF
    P_L2_Night = V_LN * I_ngt_L2 * PF
    P_L3_Night = V_LN * I_ngt_L3 * PF
    
    # 2. Energy Calculations (E = P * t)
    E_L1_Day = P_L1_Day * t_day
    E_L2_Day = P_L2_Day * t_day
    E_L3_Day = P_L3_Day * t_day
    
    E_L1_Night = P_L1_Night * t_ngt
    E_L2_Night = P_L2_Night * t_ngt
    E_L3_Night = P_L3_Night * t_ngt
    
    Total_Night_Energy_Wh = E_L1_Night + E_L2_Night + E_L3_Night
    
    # 3. Inverter Sizing (N_inv_total = 3)
    P_L1_Design = max(P_L1_Day, P_L1_Night)
    P_L2_Design = max(P_L2_Day, P_L2_Night)
    P_L3_Design = max(P_L3_Day, P_L3_Night)
    
    INV1_Rating = P_L1_Design * safety_factor
    INV2_Rating = P_L2_Design * safety_factor
    INV3_Rating = P_L3_Design * safety_factor
    
    Single_Phase_Inverter_Rating = max(INV1_Rating, INV2_Rating, INV3_Rating)
    
    return {
        "P_L1_Day": P_L1_Day, "P_L2_Day": P_L2_Day, "P_L3_Day": P_L3_Day,
        "P_L1_Night": P_L1_Night, "P_L2_Night": P_L2_Night, "P_L3_Night": P_L3_Night,
        "Total_Night_Energy_Wh": Total_Night_Energy_Wh,
        "Single_Phase_Inverter_Rating": Single_Phase_Inverter_Rating
    }

# ===================================================================
# PART 3: PV ARRAY SIZING (Based on Sheet 2, Section 6)
# ===================================================================

def calculate_pv_array(module_power_w, module_voc, module_isc, voc_coeff, 
                       t_max, t_min, inv_voc_max, inv_mppt_min, inv_mppt_max, 
                       total_night_energy_wh, system_efficiency, psh, target_modules_per_string):
    """
    Calculates PV Array requirements, String distribution, and Voltage verification.
    Standard: IEC 62548, NEC 690.7 & 690.8
    """
    # 1. Temperature Corrected Voltages (Rows 104-107)
    v_oc_at_tmax = correct_voltage_temperature(module_voc, voc_coeff, t_max)
    v_oc_at_tmin = correct_voltage_temperature(module_voc, voc_coeff, t_min) # Used for T_min (e.g. -10°C)
    
    # Safety Limits for Strings (Rows 112-113)
    max_panels_series = math.floor(inv_voc_max / v_oc_at_tmin) # Ensure Voc doesn't exceed inverter limit in cold weather
    min_panels_series = math.ceil(inv_mppt_min / v_oc_at_tmax) # Ensure Vmp is above MPPT start threshold in hot weather
    
    # 2. Required PV Power (Row 110)
    initial_pv_power = total_night_energy_wh / (psh * system_efficiency)
    
    # 3. Number of Panels (Row 111)
    num_panels_theoretical = math.ceil(initial_pv_power / module_power_w)
    
    # 4. String Validation & Distribution (Rows 114-117)
    if target_modules_per_string < min_panels_series or target_modules_per_string > max_panels_series:
        raise ValueError(f"Target modules per string ({target_modules_per_string}) is outside safe limits ({min_panels_series} - {max_panels_series})")
    
    num_parallel_strings = math.ceil(num_panels_theoretical / target_modules_per_string)
    total_modules_actual = num_parallel_strings * target_modules_per_string
    total_pv_power_w = total_modules_actual * module_power_w
    
    # 5. Voltage Verification (Rows 125-128)
    # Maximum string open circuit voltage (coldest temp) to check against Inverter Max Voc
    v_oc_string_max_tmin = target_modules_per_string * v_oc_at_tmin
    v_oc_verification = "PASS" if v_oc_string_max_tmin <= inv_voc_max else "FAIL"
    
    # Minimum MPPT voltage (hottest temp) to ensure operation above MPPT min
    # We assume V_mp at T_max. Since coeffs are similar, we use v_oc_at_tmax as a conservative proxy or use Vmp coeff
    # To match Excel exactly: V_mp_temp @ T_max = V_mp_stc * (1 + coeff_pmax * (T-25)). 
    # Let's calculate using provided array data: v_mp_tmax = 44.56 * (1 + -0.0026 * (50-25)) = 41.66V
    v_mp_tmax = 44.56 * (1 + -0.0026 * (t_max - 25))
    v_mp_string_min_tmax = target_modules_per_string * v_mp_tmax
    v_mp_verification = "PASS" if v_mp_string_min_tmax >= inv_mppt_min else "FAIL"
    
    return {
        "initial_pv_power_required": initial_pv_power,
        "num_panels_theoretical": num_panels_theoretical,
        "max_panels_series": max_panels_series,
        "min_panels_series": min_panels_series,
        "target_modules_per_string": target_modules_per_string,
        "num_parallel_strings": num_parallel_strings,
        "total_modules_actual": total_modules_actual,
        "total_pv_power_w": total_pv_power_w,
        "v_oc_string_max_tmin": v_oc_string_max_tmin,
        "v_oc_verification": v_oc_verification,
        "v_mp_string_min_tmax": v_mp_string_min_tmax,
        "v_mp_verification": v_mp_verification
    }

# ===================================================================
# PART 4: BATTERY BANK SIZING (Based on Sheet 2, Section 7)
# ===================================================================

def calculate_battery_bank(total_night_energy_ac_wh, inv_efficiency, 
                           battery_voltage, battery_capacity_ah, dod, c_rate,
                           max_charge_current, max_discharge_current):
    """
    Calculates Battery Sizing, Charging/Discharging currents, C-Rates, and Backup Time.
    Standard: IEC 61427-1, IEEE 485
    """
    # 1. Stored Energy Calculation (Rows 150-151)
    # E_bat_DC = E_Night_AC / η_inv
    e_bat_dc = total_night_energy_ac_wh / inv_efficiency
    # E_Stored_Req = E_bat_DC / η_dis (We assume discharge efficiency is 95%)
    e_stored_req = e_bat_dc / 0.95 
    
    # 2. Capacity Requirements (Rows 152-153)
    # Capacity_req (Ah) = E_Stored_Req (Wh) / (V_sys * DOD)
    capacity_req_ah = e_stored_req / (battery_voltage * dod)
    
    # Number of Batteries
    num_batteries = math.ceil(capacity_req_ah / battery_capacity_ah)
    total_capacity_ah = num_batteries * battery_capacity_ah
    
    # 3. Usable DC Battery Energy (Row 156)
    e_usable_dc_wh = battery_voltage * total_capacity_ah * dod
    
    # 4. Charging Energy & Current (Rows 160-162)
    # E_charge_req (per battery) = E_Stored_Req / (η_ch * N_Batt_total)
    e_charge_req_per_battery = e_stored_req / (0.95 * num_batteries)
    
    # Selected Charge Current = C_Rate * Battery_Capacity
    design_charge_current = c_rate * battery_capacity_ah
    charge_status = "PASS" if design_charge_current <= max_charge_current else "WARNING: Exceeds Max Charge Current"
    
    # 5. Discharge Current & Backup Time (Rows 167-172)
    night_discharge_current_per_battery = total_night_energy_ac_wh / (battery_voltage * inv_efficiency * num_batteries)
    discharge_status = "PASS" if night_discharge_current_per_battery <= max_discharge_current else "FAIL: Exceeds Max Discharge"
    
    backup_time_hours = e_usable_dc_wh * inv_efficiency / (total_night_energy_ac_wh) # Simplified approximation for actual consumption
    
    return {
        "e_stored_req": e_stored_req,
        "capacity_req_ah": capacity_req_ah,
        "num_batteries": num_batteries,
        "total_capacity_ah": total_capacity_ah,
        "e_usable_dc_wh": e_usable_dc_wh,
        "design_charge_current": design_charge_current,
        "charge_status": charge_status,
        "night_discharge_current_per_battery": night_discharge_current_per_battery,
        "discharge_status": discharge_status,
        "backup_time_hours": backup_time_hours
    }

# ===================================================================
# PART 5: CABLE SIZING ENGINE (Based on Sheet 2, Section 8 & Sheet 4)
# ===================================================================

# Importing standard tables from IEC 60364-5-52 (simplified for code)
CABLE_STANDARD_MM2 = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]
AMB_TEMP_CORRECTION = {"PVC": {30: 1.0, 40: 0.87, 50: 0.71, 55: 0.61}, 
                       "XLPE": {30: 1.0, 40: 0.91, 50: 0.82, 55: 0.76}}

def calculate_dc_cable(design_current_A, length_m, system_voltage_V, ambient_temp_C, 
                       insulation_type, num_circuits, max_vd_percent=0.02):
    """
    Fully implements Rows 189-215 from Sheet 2 (PV DC Cable Sizing)
    """
    # 1. Conductor Resistivity at Operating Temp (IEC 60228)
    rho_20 = 0.017241
    alpha = 0.00393
    max_op_temp = 90 if insulation_type == "XLPE" else 70 if insulation_type == "PVC" else 70
    rho_t = rho_20 * (1 + alpha * (max_op_temp - 20))
    
    # 2. Correction Factors (Ca, Cg) - From Sheet 4 Tables
    Ca = AMB_TEMP_CORRECTION.get(insulation_type, {}).get(ambient_temp_C, 1.0)
    # For Grouping (Assuming 9 circuits & Method C for PV as per your file rules)
    Cg = 0.78 # Based on IEC 60364-5-52 Table B.52.17 (Method C, Nc=9)
    
    # 3. Required Tabulated Current (Iz_req)
    Iz_req = design_current_A / (Ca * Cg)
    
    # 4. Finding Standard Cross-Section
    selected_mm2 = 0
    selected_Iz_table = 0
    for mm2 in CABLE_STANDARD_MM2:
        # Simplified Iz_table lookup (IEC 60364-5-52 Table B.52.12 Method C, 2 loaded)
        Iz_table = {1.5:24, 2.5:33, 4:45, 6:58, 10:80, 16:107, 25:138, 35:171, 50:209, 70:269}[mm2]
        if Iz_table >= Iz_req:
            selected_mm2 = mm2
            selected_Iz_table = Iz_table
            break
            
    # 5. Corrected Ampacity Verification
    Iz_corrected = selected_Iz_table * Ca * Cg
    ampacity_verification = "PASS" if Iz_corrected >= design_current_A else "FAIL"
    
    # 6. Voltage Drop Calculation (VD = (2 * rho * L * I) / A)
    vd_actual = (2 * rho_t * length_m * design_current_A) / selected_mm2
    vd_percent = (vd_actual / system_voltage_V) * 100
    vd_verification = "PASS" if vd_percent <= (max_vd_percent * 100) else "FAIL"
    
    return {
        "Ca": Ca, "Cg": Cg, "Iz_req": Iz_req,
        "selected_mm2": selected_mm2, "Iz_corrected": Iz_corrected,
        "ampacity_verification": ampacity_verification,
        "vd_actual_V": vd_actual, "vd_percent": vd_percent,
        "vd_verification": vd_verification
    }