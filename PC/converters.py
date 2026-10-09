from config import REF_CONDITIONS, NL_TO_SCFM

def convert_flow(flow_raw: float, pressure_gauge: float, flow_unit: str, temperature_c: float, atm_pressure: float = 1.01325) -> float:
    """Converte la portata grezza nell'unità specificata applicando pressione e temperatura."""
    ref = REF_CONDITIONS.get(flow_unit)
    if ref is None:
        return flow_raw

    P_abs = pressure_gauge + atm_pressure
    T_k = temperature_c + 273.15

    if P_abs < 0.2 or T_k < 200:
        return flow_raw

    q = flow_raw * (P_abs / ref["Pn"]) * (ref["Tn"] / T_k)

    if ref["unit"] == "SCFM":
        q *= NL_TO_SCFM
    return q