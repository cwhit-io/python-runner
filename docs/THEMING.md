# Theming Guide

## Unfold Admin Theming

Unfold supports custom theming through the `UNFOLD` configuration in `settings.py`.

### Built-in Themes

Unfold comes with pre-built themes. To use one, set the `THEME` option:

```python
UNFOLD = {
    "THEME": "blue",  # Options: "green", "blue", "purple", "red", "yellow", "monochrome"
    # ...
}
```

### Custom Colors

You can define custom colors using RGB values (without commas, space-separated):

```python
UNFOLD = {
    "COLORS": {
        "primary": {
            "50": "239 246 255",   # Lightest
            "100": "219 234 254",
            "200": "191 219 254",
            "300": "147 197 253",
            "400": "96 165 250",
            "500": "59 130 246",   # Main color
            "600": "37 99 235",
            "700": "29 78 216",
            "800": "30 64 175",
            "900": "30 58 138",
            "950": "23 37 84",     # Darkest
        },
    },
}
```

### Matching daisyUI Colors

To match your daisyUI theme colors with Unfold, you'll need to convert the colors to RGB format.

#### Example: Converting daisyUI Primary Color

1. Open your browser's DevTools on the frontend
2. Inspect an element with the primary color
3. Get the computed color (e.g., `rgb(139, 92, 246)`)
4. Convert to Unfold format: `"139 92 246"` (spaces, no commas)

#### Pre-made Color Palettes

**Purple/Violet Theme (matches daisyUI default):**

```python
"COLORS": {
    "primary": {
        "50": "245 243 255",
        "100": "237 233 254",
        "200": "221 214 254",
        "300": "196 181 253",
        "400": "167 139 250",
        "500": "139 92 246",   # Main primary
        "600": "124 58 237",
        "700": "109 40 217",
        "800": "91 33 182",
        "900": "76 29 149",
        "950": "46 16 101",
    },
}
```

**Emerald/Green Theme:**

```python
"COLORS": {
    "primary": {
        "50": "236 253 245",
        "100": "209 250 229",
        "200": "167 243 208",
        "300": "110 231 183",
        "400": "52 211 153",
        "500": "16 185 129",   # Main primary
        "600": "5 150 105",
        "700": "4 120 87",
        "800": "6 95 70",
        "900": "6 78 59",
        "950": "2 44 34",
    },
}
```

**Blue Theme:**

```python
"COLORS": {
    "primary": {
        "50": "239 246 255",
        "100": "219 234 254",
        "200": "191 219 254",
        "300": "147 197 253",
        "400": "96 165 250",
        "500": "59 130 246",   # Main primary
        "600": "37 99 235",
        "700": "29 78 216",
        "800": "30 64 175",
        "900": "30 58 138",
        "950": "23 37 84",
    },
}
```

### Dark Mode

Unfold has built-in dark mode support! Users can toggle between light and dark mode using the theme switcher in the admin interface. The colors automatically adapt.

### Tips

1. **Keep it simple**: Start with a built-in theme, then customize if needed
2. **Consistency**: The "500" shade is your main color - make sure it has good contrast
3. **Testing**: Test both light and dark modes after changing colors
4. **Generator**: Use a Tailwind color generator to create complete palettes from a single color

### Useful Tools

- [Tailwind Color Generator](https://uicolors.app/create)
- [Coolors Palette Generator](https://coolors.co/)
- [Adobe Color](https://color.adobe.com/)
