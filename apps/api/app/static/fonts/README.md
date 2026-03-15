# PDF Print Fonts

This directory contains local fonts for deterministic PDF rendering.

## Required Fonts

Download the following fonts from [Google Fonts](https://fonts.google.com/noto):

### Noto Sans (Primary body font)
- `NotoSans-Regular.woff2`
- `NotoSans-Bold.woff2`
- `NotoSans-Italic.woff2`

### Noto Serif (Headings and quotes)
- `NotoSerif-Regular.woff2`
- `NotoSerif-Bold.woff2`

### Noto Mono (Code blocks)
- `NotoMono-Regular.woff2`

## Quick Download

```bash
# Run from this directory
./download_fonts.sh
```

## Why Local Fonts?

Local fonts ensure:
1. **Reproducibility**: Same PDF output across all environments
2. **Offline capability**: No external CDN dependencies
3. **Predictable line breaks**: Font metrics are identical everywhere
4. **Cyrillic support**: Noto fonts have excellent Unicode coverage

## License

Noto fonts are licensed under SIL Open Font License (OFL).


