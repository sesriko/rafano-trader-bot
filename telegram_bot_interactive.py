def parse_broker_summary(data: Optional[Dict[str, Any]]) -> str:
    if not data:
        return "N/A"
    
    # Menyesuaikan dengan struktur respons endpoint broker-summary
    payload = data.get("data", data)
    buyers = []
    if isinstance(payload, dict):
        buyers = payload.get("buyers", payload.get("top_buyers", payload.get("data", [])))
    elif isinstance(payload, list):
        buyers = payload
        
    if not buyers:
        return "Normal/Flat"
    
    formatted = []
    for b in buyers[:3]:
        if not isinstance(b, dict):
            continue
        code = b.get("broker", b.get("broker_code", b.get("code", "???")))
        avg_price = b.get("avg_price", b.get("average", b.get("avg", 0)))
        value = b.get("value", b.get("net_value", b.get("val", 0)))
        
        val_str = ""
        try:
            if value is not None:
                abs_val = abs(float(value))
                if abs_val >= 1e9:
                    val_str = f"Rp{float(value)/1e9:.1f}B"
                elif abs_val >= 1e6:
                    val_str = f"Rp{float(value)/1e6:.1f}M"
                else:
                    val_str = f"Rp{float(value):,.0f}"
        except Exception:
            pass
                
        try:
            if avg_price and float(avg_price) > 0 and val_str:
                formatted.append(f"{code}(@Rp{float(avg_price):,.0f}|{val_str})")
            elif avg_price and float(avg_price) > 0:
                formatted.append(f"{code}(@Rp{float(avg_price):,.0f})")
            else:
                formatted.append(code)
        except Exception:
            formatted.append(str(code))
            
    return ", ".join(formatted) if formatted else "Normal/Flat"
