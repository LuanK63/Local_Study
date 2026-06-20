import unicodedata

def search_combinations():
    original = "xin chào"
    print(f"Original: {original} (hex: {original.encode('utf-8').hex()})")

    encodings = ["utf-8", "cp1252", "cp1258", "latin1", "utf-16", "utf-16le", "utf-16be"]

    for api_decode in encodings:
        try:
            source_bytes = original.encode("utf-8")
            source_str = source_bytes.decode(api_decode)
        except Exception:
            continue

        for file_encode in encodings:
            try:
                file_bytes = source_str.encode(file_encode)
            except Exception:
                continue

            for comp_in in encodings:
                for comp_out in encodings:
                    try:
                        comp_str = file_bytes.decode(comp_in)
                        exe_bytes = comp_str.encode(comp_out)
                    except Exception:
                        continue

                    for sub_decode in encodings:
                        try:
                            captured_str = exe_bytes.decode(sub_decode)
                        except Exception:
                            continue

                        # Normalize both to NFC and NFD to check for equivalence
                        nfc_str = unicodedata.normalize("NFC", captured_str)
                        nfd_str = unicodedata.normalize("NFD", captured_str)
                        
                        target_nfc = unicodedata.normalize("NFC", "chÀo")
                        target_nfd = unicodedata.normalize("NFD", "chÀo")

                        if target_nfc in nfc_str or target_nfd in nfd_str or "chÀo" in captured_str:
                            print(f"FOUND MATCH:")
                            print(f"  API Decode: {api_decode}")
                            print(f"  File Encode: {file_encode}")
                            print(f"  Compiler Input Charset: {comp_in}")
                            print(f"  Compiler Exec Charset: {comp_out}")
                            print(f"  Subprocess Decode: {sub_decode}")
                            print(f"  Result (NFC): {repr(nfc_str)}")
                            print("-" * 40)

if __name__ == "__main__":
    search_combinations()
