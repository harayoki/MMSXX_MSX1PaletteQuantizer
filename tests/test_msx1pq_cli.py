import binascii
import os
import random
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
import unittest


def _parse_png_metadata(png_bytes: bytes):
    signature = b"\x89PNG\r\n\x1a\n"
    if not png_bytes.startswith(signature):
        raise ValueError("Invalid PNG signature")

    offset = len(signature)
    width = height = bit_depth = color_type = None
    palette: list[tuple[int, int, int]] = []

    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]
        chunk_data = png_bytes[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if chunk_type == b"IHDR":
            (
                width,
                height,
                bit_depth,
                color_type,
                _compression,
                _filter,
                _interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"PLTE":
            if length % 3 != 0:
                raise ValueError("Invalid PLTE chunk length")
            palette = [
                tuple(chunk_data[i : i + 3]) for i in range(0, length, 3)
            ]
        elif chunk_type == b"IEND":
            break

    return {
        "width": width,
        "height": height,
        "bit_depth": bit_depth,
        "color_type": color_type,
        "palette": palette,
    }


def _make_sample_png_bytes() -> bytes:
    width, height = 256, 192
    # Colorful pattern for visual confirmation
    pixels = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            r = (x * 3) % 256
            g = (y * 5) % 256
            b = ((x + y) * 7) % 256
            row.extend([r, g, b, 255])
        pixels.append(bytes(row))

    raw_data = b"".join(b"\x00" + row for row in pixels)  # Add filter byte per row

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", binascii.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(raw_data))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


@unittest.skipUnless(os.name == "nt", "Windows-only CLI tests")
class Msx1pqCliTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parents[1]
        cls.cli_path = cls.repo_root / "platform" / "Win" / "x64" / "msx1pq_cli.exe"
        cls.tests_dir = Path(__file__).parent
        cls.output_root = cls.tests_dir / "msx1pq_outputs"

        if not cls.cli_path.exists():
            raise FileNotFoundError(
                f"CLI binary not found at {cls.cli_path}. Ensure the Windows build artifact is present before running tests."
            )

        # Clean previous outputs before the new test run starts.
        if cls.output_root.exists():
            shutil.rmtree(cls.output_root)
        cls.output_root.mkdir(parents=True, exist_ok=True)

        cls.sample_png_bytes = _make_sample_png_bytes()
        cls.input_image = cls._locate_or_create_input()

    @classmethod
    def _locate_or_create_input(cls) -> Path:
        candidate_pngs = sorted(
            p for p in cls.tests_dir.glob("*.png") if p.name.lower() != "msx1pq_autogen_input.png"
        )
        if candidate_pngs:
            return candidate_pngs[0]

        png_path = cls.tests_dir / "msx1pq_autogen_input.png"
        png_path.write_bytes(cls.sample_png_bytes)
        return png_path

    def _write_sample_png(self, directory: Path, name: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        png_path = directory / name
        png_path.write_bytes(self.sample_png_bytes)
        return png_path

    def _run_cli(self, input_path: Path, output_dir: Path, extra_args: list[str]):
        cmd = [str(self.cli_path), "--input", str(input_path), "--output", str(output_dir)] + extra_args
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

    def _run_cli_inputs(self, input_paths: list[Path], output_dir: Path, extra_args: list[str]):
        cmd = [str(self.cli_path), "--inputs", *map(str, input_paths), "--output", str(output_dir)] + extra_args
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

    def test_basic_png_output(self):
        output_dir = self.output_root / "basic_force"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_prefix = "basic_force_"
        result = self._run_cli(
            self.input_image,
            output_dir,
            ["--out-prefix", output_prefix, "--force"],
        )

        expected_output = output_dir / f"{output_prefix}{self.input_image.name}"
        self.assertTrue(
            expected_output.exists(),
            f"Output file not created. stdout={result.stdout}, stderr={result.stderr}",
        )

    def test_prefix_suffix_and_adjustments(self):
        output_dir = self.output_root / "prefix_suffix_adjustments"
        output_dir.mkdir(parents=True, exist_ok=True)

        prefix = "msx2_nodither_"
        suffix = "_rgb_w0.9-0.4-0.6"
        result = self._run_cli(
            self.input_image,
            output_dir,
            [
                "--out-prefix",
                prefix,
                "--out-suffix",
                suffix,
                "--color-system",
                "msx2",
                "--no-dither",
                "--no-dark-dither",
                "--no-preprocess",
                "--8dot",
                "fast",
                "--distance",
                "rgb",
                "--weight-r",
                "0.9",
                "--weight-g",
                "0.4",
                "--weight-b",
                "0.6",
                "--pre-posterize",
                "8",
                "--pre-sat",
                "0.5",
                "--pre-gamma",
                "0.8",
                "--pre-contrast",
                "1.2",
                "--pre-hue",
                "15",
                "--disable-colors",
                "2",
                "4-5",
                "--force",
            ],
        )

        expected_output = output_dir / f"{prefix}{self.input_image.stem}{suffix}{self.input_image.suffix}"
        self.assertTrue(
            expected_output.exists(),
            f"Prefixed/suffixed output missing. stdout={result.stdout}, stderr={result.stderr}",
        )

    def test_edge_emphasis_output(self):
        output_dir = self.output_root / "edge_emphasis"
        output_dir.mkdir(parents=True, exist_ok=True)

        prefix = "edge_"
        result = self._run_cli(
            self.input_image,
            output_dir,
            [
                "--out-prefix",
                prefix,
                "--pre-sharpen-black",
                "1.5",
                "--distance",
                "rgb",
                "--force",
            ],
        )

        expected_output = output_dir / f"{prefix}{self.input_image.name}"
        self.assertTrue(
            expected_output.exists(),
            f"Edge emphasis output missing. stdout={result.stdout}, stderr={result.stderr}",
        )

    def test_sc2_output_and_palette_options(self):
        output_dir = self.output_root / "sc2_palette92_best_attr"
        output_dir.mkdir(parents=True, exist_ok=True)

        input_dir = self.output_root / "sc2_inputs"
        first_input = self._write_sample_png(input_dir, "first_input.png")
        second_input = self._write_sample_png(input_dir, "second_input.png")

        prefix = "sc2_bestattr_palette92_"
        result = self._run_cli(
            input_dir,
            output_dir,
            [
                "--out-prefix",
                prefix,
                "--out-sc2",
                "--8dot",
                "best-attr",
                "--distance",
                "hsv",
                "--palette92",
                "--dither",
                "--dark-dither",
                "--weight-h",
                "0.7",
                "--weight-s",
                "0.3",
                "--weight-b",
                "0.9",
                "--force",
            ],
        )

        expected_first = output_dir / f"{prefix}{first_input.stem}.sc2"
        expected_second = output_dir / f"{prefix}{second_input.stem}.sc2"
        self.assertTrue(
            expected_first.exists() and expected_second.exists(),
            f"SC2 outputs missing. stdout={result.stdout}, stderr={result.stderr}",
        )

    def test_multiple_inputs_mode(self):
        output_dir = self.output_root / "multi_inputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        inputs_dir = self.output_root / "multi_input_sources"
        first_input = self._write_sample_png(inputs_dir, "multi_first.png")
        second_input = self._write_sample_png(inputs_dir, "multi_second.png")

        prefix = "multi_"
        suffix = "_processed"
        result = self._run_cli_inputs(
            [first_input, second_input],
            output_dir,
            ["--out-prefix", prefix, "--out-suffix", suffix, "--force"],
        )

        expected_first = output_dir / f"{prefix}{first_input.stem}{suffix}{first_input.suffix}"
        expected_second = output_dir / f"{prefix}{second_input.stem}{suffix}{second_input.suffix}"
        self.assertTrue(
            expected_first.exists() and expected_second.exists(),
            f"Multiple input outputs missing. stdout={result.stdout}, stderr={result.stderr}",
        )

    def test_randomized_parameter_runs(self):
        rng = random.Random(98765)
        output_dir = self.output_root / "randomized_runs"
        output_dir.mkdir(parents=True, exist_ok=True)

        distance_modes = ["rgb", "hsv"]
        color_systems = ["msx1", "msx2"]

        for idx in range(4):
            prefix = f"rand_{idx}_"
            args: list[str] = ["--out-prefix", prefix]

            color_system = rng.choice(color_systems)
            args.extend(["--color-system", color_system])

            args.append("--8dot")
            args.append(rng.choice(["fast", "best-attr"]))

            distance_mode = rng.choice(distance_modes)
            args.extend(["--distance", distance_mode])

            if rng.choice([True, False]):
                args.append("--no-dither")
            else:
                args.append("--dither")

            if rng.choice([True, False]):
                args.append("--no-dark-dither")
            else:
                args.append("--dark-dither")

            if distance_mode == "hsv":
                weight_h = f"{rng.uniform(0.4, 1.0):.2f}"
                weight_s = f"{rng.uniform(0.2, 0.8):.2f}"
                weight_v = f"{rng.uniform(0.5, 1.0):.2f}"
                args.extend(["--weight-h", weight_h, "--weight-s", weight_s, "--weight-v", weight_v])
            else:
                weight_r = f"{rng.uniform(0.4, 1.0):.2f}"
                weight_g = f"{rng.uniform(0.2, 0.8):.2f}"
                weight_b = f"{rng.uniform(0.5, 1.0):.2f}"
                args.extend(["--weight-r", weight_r, "--weight-g", weight_g, "--weight-b", weight_b])

            if rng.choice([True, False]):
                args.extend(["--pre-posterize", str(rng.choice([6, 8, 10]))])

            args.append("--force")

            result = self._run_cli(self.input_image, output_dir, args)

            expected_output = output_dir / f"{prefix}{self.input_image.name}"
            self.assertTrue(
                expected_output.exists(),
                (
                    "Randomized output missing. "
                    f"stdout={result.stdout}, stderr={result.stderr}, args={args}"
                ),
            )

    def test_palette_png_scaling_and_palette_order(self):
        output_dir = self.output_root / "palette_scale"
        output_dir.mkdir(parents=True, exist_ok=True)

        result = self._run_cli(
            self.input_image, output_dir, ["--scale", "3", "--force"]
        )

        expected_output = output_dir / self.input_image.name
        self.assertTrue(
            expected_output.exists(),
            f"Scaled palette PNG missing. stdout={result.stdout}, stderr={result.stderr}",
        )

        metadata = _parse_png_metadata(expected_output.read_bytes())

        self.assertEqual(3, metadata["color_type"])
        self.assertEqual((256 * 3, 192 * 3), (metadata["width"], metadata["height"]))
        self.assertEqual(8, metadata["bit_depth"])

        expected_palette = [
            (0, 0, 0),  # index 0 transparent black
            (0, 0, 0),  # 1: 黒
            (62, 184, 73),  # 2: 緑
            (116, 208, 125),  # 3: 薄緑
            (89, 85, 224),  # 4: 紫
            (128, 118, 241),  # 5: 薄紫
            (185, 94, 81),  # 6: 赤
            (101, 219, 239),  # 7: 水色
            (219, 101, 89),  # 8: 赤紫
            (255, 137, 125),  # 9: ピンク
            (204, 195, 94),  # 10: 黄土色
            (222, 208, 135),  # 11: 明るい黄色
            (58, 162, 65),  # 12: 深緑
            (183, 102, 181),  # 13: 赤紫
            (204, 204, 204),  # 14: 灰色
            (255, 255, 255),  # 15: 白
        ]

        self.assertEqual(
            expected_palette,
            metadata["palette"],
            f"Palette entries mismatch. stdout={result.stdout}, stderr={result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
