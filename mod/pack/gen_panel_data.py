"""개발용(앱에 넣지 않음): 로컬 도구가 만든 산출물(app_inputs 폴더)에서 앱이 쓰는 데이터 파일을 만든다.
사용: python gen_panel_data.py <app_inputs 폴더> [v1 조각 폴더(cave_out)]
 -> panel_code.json (DLL 단계), panel_spec.json, panel_sprites.json, 그리고 번들 빌더 모듈(itdp_*.py)을 이 폴더에 복사/변환한다."""
import json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1]
v1dir = sys.argv[2] if len(sys.argv) > 2 else None
L = json.load(open(os.path.join(src, "layout.json"), encoding="utf-8"))
sec = open(os.path.join(src, "section_itd2.bin"), "rb").read()
assert len(sec) == 0x800
hk = L["hook"]
V1 = [("HELP", 0x5A0, "cave_help.bin"), ("FAMS", 0x620, "table_fams.bin"), ("TAIL", 0x7B0, "cave_tail.bin"), ("ROWS", 0x830, "table_rows.bin"), ("MAIN", 0xD60, "cave_main.bin")]
pieces = []
if v1dir:
    for n, po, fn in V1:
        pieces.append({"name": n, "page_off": po, "hex": open(os.path.join(v1dir, fn), "rb").read().hex()})
D = {"section_hex": sec.hex(), "itd2_header_off": int(L["section"]["header_file_offset"], 16), "itd2_header_hex": L["section"]["header_bytes"].replace(" ", ""),
     "hook_off": int(hk["file_offset"], 16), "hook_orig": hk["orig"].replace(" ", ""), "hook_new": hk["new"].replace(" ", ""),
     "hook_before": "33d2c7442430ffffffff488d4c2430e8fdd00000", "hook_after": "488d4c2420e84bc4bbff4c8d9c2480000000498b",
     "v1_pieces": pieces, "v1_hook_new": "e968ff7f05909090"}
json.dump(D, open(os.path.join(HERE, "panel_code.json"), "w", encoding="utf-8"), indent=0)
print("panel_code.json:", len(D["section_hex"]) // 2, "바이트 구역, 후크", D["hook_new"], "v1 조각", len(pieces))
