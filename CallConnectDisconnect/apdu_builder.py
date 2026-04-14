import re

def to_hex(byte_array):
    return ' '.join(f'{b:02X}' for b in byte_array)

def from_hex(hex_string):
    hex_string = re.sub(r'\s+', '', hex_string.upper())
    if len(hex_string) % 2 != 0:
        raise ValueError("Hex string must have an even number of characters.")
    return bytearray.fromhex(hex_string)

def build_length(length):
    if length < 0x80:
        return [length]
    elif length <= 0xFF:
        return [0x81, length]
    else:
        return [0x82, length >> 8, length & 0xFF]

def build_tlv(tag, value):
    if isinstance(value, str):
        value = from_hex(value)
    elif isinstance(value, int):
        value = [value]
    elif isinstance(value, list) or isinstance(value, bytearray):
        pass
    else:
        raise ValueError("Unsupported value type")
        
    value = list(value)
    length = build_length(len(value))
    return [tag] + length + value

def encode_bcd(digits):
    # Padding with F if odd length
    digits = str(digits)
    if len(digits) % 2 != 0:
        digits += 'F'
        
    bcd = []
    for i in range(0, len(digits), 2):
        # BCD format generally swaps nibbles for phone numbers in SMS/Call records
        high = digits[i+1] if digits[i+1] != 'F' else 'F'
        low = digits[i]
        bcd.append(int(high + low, 16))
    return bcd

def address_tlv(phone_number, ton_npi=None):
    # Tag 0x86 (Address) or 0x06 (without CR) - let's use 0x86 
    # TON/NPI byte (0x81 = Unknown/ISDN, 0x91 = International/ISDN)
    
    if phone_number.startswith('+'):
        ton_npi = 0x91
        number = phone_number[1:]
    else:
        if ton_npi is None:
            ton_npi = 0x81
        number = phone_number
        
    bcd_digits = encode_bcd(number)
    return build_tlv(0x86, [ton_npi] + bcd_digits)

def transaction_id_tlv(ti):
    return build_tlv(0x9C, ti)

def device_identities_tlv(source, dest):
    return build_tlv(0x82, [source, dest])

def build_envelope(data_tlv_content):
    # Envelope command: 80 C2 00 00 Lc [D6 Length Data]
    event_download_tlv = build_tlv(0xD6, data_tlv_content)
    
    header = [0x80, 0xC2, 0x00, 0x00]
    lc = len(event_download_tlv)
    
    # We assume Lc fits in 1 byte for most standard event downloads.
    # If Lc > 255, extended APDU would be needed (00 00 Lc1 Lc2), but event downloads are short.
    apdu = header + [lc] + event_download_tlv
    return apdu

def build_mt_call_envelope(ti, phone_number):
    # Event list: 00 (MT call) - Tag 0x99
    event_list = build_tlv(0x99, [0x00])
    
    # Device identities: Network (0x83) to UICC (0x81)
    dev_ids = device_identities_tlv(0x83, 0x81)
    
    # Transaction ID
    tid = transaction_id_tlv([from_hex(ti)[0]])
    
    # Address
    address = address_tlv(phone_number)
    
    data = event_list + dev_ids + tid + address
    return build_envelope(data)

def build_call_connected_envelope(ti):
    # Event list: 01 (Call connected) - Tag 0x99
    event_list = build_tlv(0x99, [0x01])
    
    # Device identities: ME (0x82) to UICC (0x81) for MO, or Network (0x83) to UICC (0x81) for MT
    # We will use ME (0x82) as default for connected
    dev_ids = device_identities_tlv(0x82, 0x81)
    
    # Transaction ID
    tid = transaction_id_tlv([from_hex(ti)[0]])
    
    data = event_list + dev_ids + tid
    return build_envelope(data)

def build_call_disconnected_envelope(ti, cause_hex):
    # Event list: 02 (Call disconnected) - Tag 0x99
    event_list = build_tlv(0x99, [0x02])
    
    # Device identities: ME (0x82) to UICC (0x81)
    dev_ids = device_identities_tlv(0x82, 0x81)
    
    # Transaction ID
    tid = transaction_id_tlv([from_hex(ti)[0]])
    
    # Cause: Tag 0x9A
    cause = build_tlv(0x9A, from_hex(cause_hex))
    
    data = event_list + dev_ids + tid + cause
    return build_envelope(data)

def build_terminal_profile(profile_hex):
    # TERMINAL PROFILE command: 80 10 00 00 Lc [Profile Data]
    profile_data = from_hex(profile_hex)
    header = [0x80, 0x10, 0x00, 0x00]
    lc = len(profile_data)
    return header + [lc] + list(profile_data)

if __name__ == "__main__":
    # Simple tests
    print("MT Call:")
    print(to_hex(build_mt_call_envelope("01", "1234567")))
    
    print("\nCall Connected:")
    print(to_hex(build_call_connected_envelope("01")))
    
    print("\nCall Disconnected:")
    print(to_hex(build_call_disconnected_envelope("01", "8090")))
