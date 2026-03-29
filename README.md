# win2kde-cursor-converter

Convert Windows `.ani` / `.cur` cursor packs into Linux Xcursor themes with a GUI workflow.

## Dependencies

Arch / CachyOS:

```bash
sudo pacman -S --needed python tk icoutils xorg-xcursorgen imagemagick
```

Or run:

```bash
./scripts/install-deps-arch.sh
```

Required tools:
- `python`
- `tk`
- `icotool`
- `xcursorgen`
- `magick` or `convert`

## Run

From the repo root:

```bash
python ./cursor-source-slot-mapper.py
```

You can also use:

```bash
python ./win2kde-cursor-converter.py
```

## GUI Workflow

1. Choose the Windows cursor folder.
2. Click `Auto-Fill From Pack`.
3. Fix any slot paths if needed.
4. Set the output sizes and scale filter.
5. Click `Build + Package`.
6. Install the generated `.tar.gz` cursor theme.

## What Changed

- Prepare no longer flattens cursor data into one PNG per slot.
- The saved mapping JSON keeps original source paths.
- The GUI preserves custom output sizes from loaded mappings and uses them on save/build.
- Build inspects the original `.cur` / `.ani` source at build time.
- For each requested Linux cursor size, the builder picks the smallest native Windows entry that is at least that large.
- If no native entry is large enough, the builder uses the largest native entry and scales only then.
- Animated `.ani` frames keep per-frame delays and preserve all native entries found in each embedded CUR frame.
- Auto-fill prefers top-level source assets over duplicate files under `tmp/`, `build/`, or similar folders when heuristic scores are equal.

## Output

The GUI creates:
- `_prepared/<pack-name>/mapping.json`
- `_prepared/<pack-name>/prep-summary.json`
- `_mappings/<theme-name>.json`
- `_builds/<theme-name>/` temporary extracted and built assets
- `<theme-name>/` built Linux cursor theme
- `<theme-name>.tar.gz` installable cursor archive

## Install A Built Theme

```bash
mkdir -p ~/.icons
tar -xzf /path/to/YourTheme.tar.gz -C ~/.icons
plasma-apply-cursortheme YourTheme
```

## CLI Helpers

Prepare a Windows cursor set:

```bash
python ./prepare-windows-cursor-set.py /path/to/windows-pack /path/to/output-root
```

Build from a saved mapping:

```bash
python ./build-cursor-from-mapping.py /path/to/mapping.json /path/to/output-root --theme-name YourTheme
```

If you omit `--sizes` and `--scale-filter`, the builder uses the values saved in the mapping JSON.

Choose a scaling filter when scaling is required:

```bash
python ./build-cursor-from-mapping.py /path/to/mapping.json /path/to/output-root \
  --theme-name YourTheme \
  --scale-filter point
```

Choose custom output sizes, including larger HiDPI sizes such as `256`:

```bash
python ./build-cursor-from-mapping.py /path/to/mapping.json /path/to/output-root \
  --theme-name YourTheme \
  --sizes 24,32,36,48,64,96,128,192,256
```

## Defaults

- Output sizes: `24, 32, 36, 48, 64, 96, 128, 192`
- Scale filters: `point`, `mitchell`, `lanczos`
- Default filter: `point`
- The GUI `Output sizes` field is editable and saved into `build_options.target_sizes`.

## JSON Mapping Notes

Saved mapping JSON now includes:
- `selected_slots`
- `resolved_role_map`
- `build_options`

Builder metadata JSON can now represent multiple native entries per frame:
- each frame keeps `delay_ms`
- each frame can contain `entries[]`
- each entry can carry `png`, `width`, `height`, `hotspot_x`, `hotspot_y`, and `entry_index`

Legacy flat JSON frame metadata is still accepted.

## Notes

- The builder preserves hotspots and animation delays from the Windows source where possible.
- `192` is included by default for HiDPI KDE setups.
- `256` is supported through the GUI or `--sizes`, but it is not enabled by default because many Windows packs do not contain useful native 256px cursor art and it increases output size substantially.
- Some Windows packs still need manual slot correction if filenames or `install.inf` metadata are ambiguous.
