import sys
import jinja2
import argparse
from pathlib import Path
from typing import List, Set
import tempfile
import msxdisk

# NOTE: SCREEN5 対応を廃止し、SCREEN4 対応を追加しました。

autoexec_bas = """10 RUN "V.BAS"
"""

viewer_template = """10 DEFINT A-Z:COLOR 15,0,0:CLS:KEY 6,"AUTOEXEC.BAS"
20 PRINT "MMSXX MSX1 IMAGE VIEWER v1.0"
30 PRINT "ESC TO EXIT, SPACE/DOWN NEXT, UP PREV"
# データ数を埋め込み
40 GOSUB 1000 
50 LASTI=-1:NIMG={{num_images}}:SC2MSX2={{allow_sc2_in_msx2|default(0)}}
60 GOSUB 2000
70 IF NING=0 THEN PRINT "NO SC2/SC4 IMAGES FOUND":END
80 SC=0:K$=" ":GOTO 120
100 ' ____ MAIN LOOP ____
110 K$=INKEY$
120 IF K$="" THEN 110
# スペースキーまたはカーソル下で次の画像へ
130 IF K$=" " THEN I=I+1:GOSUB 500:GOTO 110
140 IF K$=CHR$(31) THEN I=I+1:GOSUB 500:GOTO 110
# カーソル上で前の画像へ
150 IF K$=CHR$(30) THEN I=I-1:GOSUB 500:GOTO 110
# ESCキーで終了
160 IF K$=CHR$(27) THEN END
170 GOTO 110
500 ' ____ SHOW IMAGE ____
510 IF I < 0 THEN I = NIMG - 1
520 IF I >= NIMG THEN I = 0
530 IF LASTI=I THEN RETURN
540 LASTI=I
550 PRINT "IMG ";I+1;"/";NIMG;": ";F$(I)
560 IF RIGHT$(F$(I),3)="SC2" THEN GOSUB 1200 ELSE GOSUB 1300
570 BLOAD F$(I), S
580 IF RIGHT$(F$(I),3)="SC2" THEN GOSUB 1600 ELSE GOSUB 1500 
990 RETURN
1000 ' ____ MSX1/MSX2- CHECK ____
1010 MSXV=1
1020 ON ERROR GOTO 1100
1030 A=VDP(10)
1040 MSXV=2
1050 PRINT "MSX2~ DETECTED"
1060 RETURN
1070 PRINT "MSX1 DETECTED"
1080 RETURN
1100 ON ERROR GOTO 0
1110 RESUME 1070
1200 '____ SETUP SCREEN 2 ____
1210 IF SC=2 THEN RETURN
1220 SC=2:COLOR 15,0,0:KEY OFF:PRINT "SCREEN 2 SET"
1230 SCREEN 2
1290 RETURN
1300 '____ SETUP SCREEN 4 ____
1310 IF SC=4 THEN RETURN
1320 SC=4:COLOR 15,0,0:KEY OFF:PRINT "SCREEN 4 SET"
1320 SCREEN 4
1330 RETURN
1500 '____ SET PALETTE ____
1510 FOR C = 0 TO 15
1520  D1 = VPEEK(&H1B80 + C*2)
1530  D2 = VPEEK(&H1B80 + C*2 + 1)
# R2R1R0 = bit6-4
1540  R = (D1 AND &H70) / 16
# B2B1B0 = bit2-0
1550  B = (D1 AND &H07)
# G2G1G0 = bit2-0
1560  G = (D2 AND &H07)
1570  COLOR=(C,R,G,B)
1580 NEXT C
1590 RETURN
# 手動でパレットを背艇する場合は以下を実行
1600 '____ MANUAL PALETTE SET ____
1630 COLOR=(0,0,0,0)
1640 COLOR=(1,0,0,0)
1650 COLOR=(2,2,5,2)
1660 COLOR=(3,3,5,3)
1670 COLOR=(4,2,2,6)
1680 COLOR=(5,3,3,6)
1690 COLOR=(6,5,2,2)
1700 COLOR=(7,2,6,6)
1710 COLOR=(8,6,2,2)
1720 COLOR=(9,7,3,3)
1730 COLOR=(10,5,5,2)
1740 COLOR=(11,6,5,3)
1750 COLOR=(12,1,4,1)
1760 COLOR=(13,5,3,5)
1770 COLOR=(14,5,5,5)
1780 COLOR=(15,7,7,7)
1990 RETURN
2000 '____ LOAD DATA ____
2020 DIM F$(NIMG-1):I = 0
2030 READ D$
2040 IF D$="END" THEN NING=I:RETURN
2050 IF RIGHT$(D$,3)="SC4" AND MSXV=1 THEN GOTO 2030
2060 IF RIGHT$(D$,3)="SC2" AND MSXV=2 AND SC2MSX2=0 THEN GOTO 2030
2070 PRINT "FOUND IMG: "; D$
2080 F$(I)=D$
2090 I=I+1:GOTO 2030
3000 DATA {% for item in my_list %}"{{item}}"{% if not loop.last %},{% else%}{% endif %}{% endfor %}
3010 DATA "END"
"""

def get_name_in_dos_83(name: str) -> str:
    """Convert a filename to DOS 8.3 format."""
    p = Path(name)
    stem = p.stem.upper()[:8]
    suffix = p.suffix.lstrip('.').upper()[:3]
    if suffix:
        return f"{stem}.{suffix}"
    else:
        return stem

def get_file_list(input_paths: List[str], target_exts: Set[str]) -> List[Path]:
    def is_target(path: Path) -> bool:
        return path.suffix.lstrip('.').lower() in target_exts
    file_list = []
    for path_str in input_paths:
        path = Path(path_str)
        if path.is_dir():
            for file in path.rglob('*'):
                if file.is_file() and is_target(file):
                    file_list.append(file)
        elif path.is_file() and is_target(path):
            file_list.append(path)
    return file_list


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a MSX disk image with sc2/sc4 viewer. "
            "SCREEN5 support has been removed; SCREEN4 support is available."
        ))
    parser.add_argument(
        "input_files_or_dirs",
        nargs="+",
        type=str,
        help="Input files or directories to process",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        type=str,
        help="Output Diskimage(*.dsk) path",
    )
    parser.add_argument(
        "-s2m2",
        "--allow-sc2-in-msx2",
        default=1,
        type=int,
        help="allow sc2 files to be viewed on MSX2 machines.",
    )

    args = parser.parse_args()
    input_paths = args.input_files_or_dirs
    flatten_paths = get_file_list(input_paths, target_exts={'sc2', 'sc4'})
    if not flatten_paths:
        sys.exit("No .sc2 or .sc4 files found in the provided paths.")

    temp_dir = tempfile.TemporaryDirectory()
    for i, p in enumerate(flatten_paths):
        # 99個まで diskにそもそも50もはいらないが
        if i >= 99:
            print("Warning: Only the first 99 images will be processed.")
            break
        target_path = Path(temp_dir.name) / f"{i:02d}-{(p.name+'__')[:3]}.{p.suffix[-3:].upper()}"
        print(f"Copying {p.name} to {target_path}")
        target_path.write_bytes(p.read_bytes())
    files_in_temp = [p for p in Path(temp_dir.name).iterdir() if p.is_file()]
    template = jinja2.Template(viewer_template)
    output_lines = template.render(
        num_images=len(flatten_paths),
        allow_sc2_in_msx2=1 if args.allow_sc2_in_msx2 == 1 else 0,
        my_list=[str(p.name) for p in files_in_temp]
    ).splitlines()
    output_lines = [line for line in output_lines if not line.strip().startswith('#')] # #で始まる行を削除
    # print("")
    # for line in output_lines:
    #     print(line)
    # print("")
    viewer_bas_path = Path(temp_dir.name) / "V.BAS"
    with open(viewer_bas_path, 'w') as f:
        f.write('\n'.join(output_lines))
    autoexec_bas_path = Path(temp_dir.name) / "AUTOEXEC.BAS"
    with open(autoexec_bas_path, 'w') as f:
        f.write(autoexec_bas)
    files_in_temp = [p for p in Path(temp_dir.name).iterdir() if p.is_file()]
    for p in files_in_temp:
        print(f"Prepared file : {p.name}")
    msxdisk.create_disk_image(
        output_path=args.output,
        inputs=files_in_temp,
        ignore_extensions=None,
        allow_partial=False,
    )
    print(f"Created disk image at {args.output} with files")


if __name__ == "__main__":
    main()
