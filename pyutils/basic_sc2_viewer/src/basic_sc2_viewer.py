import sys
import jinja2
import argparse
from pathlib import Path
from typing import List, Set
import tempfile
import msxdisk

autoexec_bas_template = """10 DEFINT A-Z
20 SCREEN 2:COLOR 15,0,0:KEY OFF:CLS
# 画像ファイル数を設定
30 NIMG = {{num_images}}
40 DIM F$(NIMG-1)
50 FOR I=0 TO NIMG-1
60   READ F$(I)
70 NEXT I
80 I = 0
90 GOSUB 1000
100 K$ = INKEY$
110 IF K$="" THEN 100
# スペースキーまたはカーソル下で次の画像へ
130 IF K$=" " THEN I = I + 1:GOSUB 500:GOTO 100
140 IF K$=CHR$(31) THEN I = I + 1:GOSUB 500:GOTO 100
# カーソル上で前の画像へ
160 IF K$=CHR$(30) THEN I = I - 1:GOSUB 500:GOTO 100
# ESCキーで終了
170 IF K$=CHR$(27) THEN END
180 GOTO 100
500 IF I < 0 THEN I = NIMG - 1
510 IF I >= NIMG THEN I = 0
520 GOSUB 1000
530 RETURN
1000 'SETUP SCREEN AND LOAD IMAGE
# ファイル名がSC5ならSCREEN 5 SC2ならSCREEN 2 に設定
1010 IF RIGHT$(F$(I),3)="SC2" THEN GOTO 1300
# パレットを毎回設定する必要はないかもだが、画像によって変更する可能性はある
1020 SCREEN 5
1030 COLOR=(0,0,0,0)
1040 COLOR=(1,0,0,0)
1050 COLOR=(2,2,5,2)
1060 COLOR=(3,3,5,3)
1070 COLOR=(4,2,2,6)
1080 COLOR=(5,3,3,6)
1090 COLOR=(6,5,2,2)
1100 COLOR=(7,2,6,6)
1110 COLOR=(8,6,2,2)
1120 COLOR=(9,7,3,3)
1130 COLOR=(10,5,5,2)
1140 COLOR=(11,6,5,3)
1150 COLOR=(12,1,4,1)
1160 COLOR=(13,5,3,5)
1170 COLOR=(14,5,5,5)
1180 COLOR=(15,7,7,7)
1190 'COLOR 15,0,0:CLS
1200 GOTO 1400
1300 SCREEN 2
## パレット設定の必要あればここに書く
1310 GOTO 1400
1400 'COLOR 15,0,0:CLS
1410 BLOAD F$(I),S
1420 RETURN
1500 DATA {% for item in my_list %}"{{item}}"{% if not loop.last %},{% else%}{% endif %}{% endfor %}"""

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
        description="Create a basic MSX disk image viewer for .sc2 / .sc5 files.")
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

    args = parser.parse_args()
    input_paths = args.input_files_or_dirs
    flatten_paths = get_file_list(input_paths, target_exts={'sc2', 'sc5'})
    if not flatten_paths:
        sys.exit("No .sc2 files found in the provided paths.")

    temp_dir = tempfile.TemporaryDirectory()
    for i, p in enumerate(flatten_paths):
        target_path = Path(temp_dir.name) / f"IMG_{i:02d}.{p.suffix[-3:].upper()}"
        print(f"Copying {p.name} to {target_path}")
        target_path.write_bytes(p.read_bytes())
    files_in_temp = [p for p in Path(temp_dir.name).iterdir() if p.is_file()]
    template = jinja2.Template(autoexec_bas_template)
    output_lines = template.render(
        num_images=len(flatten_paths),
        my_list=[str(p.name) for p in files_in_temp]
    ).splitlines()
    output_lines = [line for line in output_lines if not line.strip().startswith('#')] # #で始まる行を削除
    print()
    for line in output_lines:
        print(line)
    print()
    autoexec_bas_path = Path(temp_dir.name) / "AUTOEXEC.BAS"
    with open(autoexec_bas_path, 'w') as f:
        f.write('\n'.join(output_lines))
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
