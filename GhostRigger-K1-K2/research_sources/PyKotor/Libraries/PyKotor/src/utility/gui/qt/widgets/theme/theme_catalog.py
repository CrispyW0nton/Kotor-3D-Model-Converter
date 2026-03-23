"""Built-in theme catalog. From Toolset theme_manager._build_builtin_theme_configs."""
from __future__ import annotations
from typing import Any
from qtpy.QtGui import QColor


def build_builtin_theme_configs(manager: Any) -> dict[str, dict[str, Any]]:
    """Build built-in theme configs. manager must have create_palette, _get_file_stylesheet, original_style."""
    configs: dict[str, dict[str, Any]] = {
        "native": {
            "style": manager.original_style,
            "palette": None,  # Will use standard palette
            "sheet": "",
        },
        "fusion (light)": {
            "style": "Fusion",
            "palette": lambda: manager.create_palette(
                QColor(240, 240, 240),  # primary - button/base (light gray)
                QColor(255, 255, 255),  # secondary - window background (white)
                QColor(30, 30, 30),  # text - dark text on light background
                QColor(250, 250, 250),  # tooltip base - light gray
                QColor(0, 120, 212),  # highlight - blue accent
                QColor(0, 0, 0),  # bright text - black for light theme
            ),
            "sheet": "",
        },
        "fusion (dark)": {
            "style": "Fusion",
            "palette": lambda: manager.create_palette(
                QColor(53, 53, 53),  # primary - button/base
                QColor(35, 35, 35),  # secondary - window background
                QColor(240, 240, 240),  # text - high contrast on dark
                QColor(60, 60, 60),  # tooltip base - improved visibility
                QColor(255, 160, 0),  # highlight - brighter orange for visibility
                QColor(255, 255, 255),  # bright text
            ),
            "sheet": "",
        },
        "amoled": {
            "style": "Fusion",
            # AMOLED optimized: true black background with high contrast text
            "palette": lambda: manager.create_palette("#000000", "#0A0A0A", "#E8E8E8", "#1F1F1F", "#FF8C42", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/AMOLED.qss", app),
        },
        "aqua": {
            "style": "Fusion",
            "palette": None,  # Aqua theme handles its own palette
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/aqua.qss", app),
        },
        "consolestyle": {
            "style": "Fusion",
            # Console style: dark terminal aesthetic with vibrant accent
            "palette": lambda: manager.create_palette("#000000", "#1A1A1A", "#F5F5F5", "#2A2A2A", "#FFAA00", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/ConsoleStyle.qss", app),
        },
        "elegantdark": {
            "style": "Fusion",
            # Elegant dark: sophisticated green accent on dark gray
            "palette": lambda: manager.create_palette("#2D2D2D", "#1F1F1F", "#E8E8E8", "#3D3D3D", "#52C878", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/ElegantDark.qss", app),
        },
        "macos": {
            "style": "Fusion",
            "palette": None,  # MacOS theme handles its own palette
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/MacOS.qss", app),
        },
        "manjaromix": {
            "style": "Fusion",
            # Manjaro: teal accent on dark green-gray background
            "palette": lambda: manager.create_palette("#222b2e", "#151a1e", "#FFFFFF", "#2a4037", "#5FB3B3", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/ManjaroMix.qss", app),
        },
        "materialdark": {
            "style": "Fusion",
            # Material Dark: Google Material Design colors with improved contrast
            "palette": lambda: manager.create_palette("#1E1E24", "#25242A", "#FFFFFF", "#2E2D33", "#00D9A5", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/MaterialDark.qss", app),
        },
        "cyberpunk2077": {
            "style": "Fusion",
            # Cyberpunk: neon cyan on deep purple-blue background
            "palette": lambda: manager.create_palette("#1e2033", "#262940", "#E8E5F0", "#2d3047", "#00F0E6", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/cyberpunk2077.qss", app),
        },
        "andromeda": {
            "style": "Fusion",
            # Andromeda: cyan accent on dark blue-gray
            "palette": lambda: manager.create_palette("#23262E", "#1A1C22", "#E8E5F0", "#2A2D44", "#00F0E6", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/Andromeda.qss", app),
        },
        "asunadark": {
            "style": "Fusion",
            # Asuna Dark: red accent on very dark background
            "palette": lambda: manager.create_palette("#1b1b1b", "#232323", "#F8F8F2", "#2f2f2f", "#C63A4A", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/AsunaDark.qss", app),
        },
        "asuna": {
            "style": "Fusion",
            # Asuna: matching AsunaDark palette
            "palette": lambda: manager.create_palette("#1b1b1b", "#232323", "#F8F8F2", "#2f2f2f", "#C63A4A", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/Asuna.qss", app),
        },
        "andromedaitalic": {
            "style": "Fusion",
            # Andromeda Italic: same as Andromeda
            "palette": lambda: manager.create_palette("#23262E", "#1A1C22", "#E8E5F0", "#2A2D44", "#00F0E6", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/AndromedaItalic.qss", app),
        },
        "astolfo": {
            "style": "Fusion",
            # Astolfo: pink accent on dark green-tinted background
            "palette": lambda: manager.create_palette("#1a1c19", "#241517", "#F8F8F2", "#2b2b2b", "#E8A5C7", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/Astolfo.qss", app),
        },
        "shadesofpurple": {
            "style": "Fusion",
            # Shades of Purple: vibrant purple-pink on deep purple
            "palette": lambda: manager.create_palette("#2D2B55", "#1E1E3F", "#E8E8E8", "#3D3B6D", "#FF6AD5", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/ShadesOfPurple.qss", app),
        },
        "monokaidark": {
            "style": "Fusion",
            # Monokai Dark: classic editor theme with pink accent
            "palette": lambda: manager.create_palette("#272822", "#1E1F1C", "#F8F8F2", "#49483E", "#FF6188", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/MonokaiDark.qss", app),
        },
        "solarizeddark": {
            "style": "Fusion",
            # Solarized Dark: scientifically optimized for readability
            "palette": lambda: manager.create_palette("#002B36", "#073642", "#839496", "#586E75", "#2AA198", "#FDF6E3"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/SolarizedDark.qss", app),
        },
        "onedarkpro": {
            "style": "Fusion",
            # One Dark Pro: popular VS Code theme with blue accent
            "palette": lambda: manager.create_palette("#282C34", "#21252B", "#ABB2BF", "#3E4451", "#61AFEF", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/OneDarkPro.qss", app),
        },
        "norddark": {
            "style": "Fusion",
            # Nord Dark: arctic, north-bluish color palette
            "palette": lambda: manager.create_palette("#2E3440", "#3B4252", "#E5E9F0", "#434C5E", "#88C0D0", "#ECEFF4"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/NordDark.qss", app),
        },
        "gruvboxdark": {
            "style": "Fusion",
            # Gruvbox Dark: retro groove color scheme
            "palette": lambda: manager.create_palette("#282828", "#1D2021", "#EBDBB2", "#3C3836", "#FE8019", "#FB4934"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/GruvboxDark.qss", app),
        },
        "draculadark": {
            "style": "Fusion",
            # Dracula Dark: dark theme with vibrant accents
            "palette": lambda: manager.create_palette("#282A36", "#1E1F29", "#F8F8F2", "#44475A", "#BD93F9", "#FF79C6"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/DraculaDark.qss", app),
        },
        "ubuntu": {
            "style": "Fusion",
            # Ubuntu Yaru: light theme with Ubuntu orange accent (#E95420)
            "palette": lambda: manager.create_palette("#FFFFFF", "#F5F5F5", "#2D2D2D", "#FFFFFF", "#E95420", "#FFFFFF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/Ubuntu.qss", app),
        },
        "neonbuttons": {
            "style": "Fusion",
            # Neon Buttons: vibrant neon aesthetic
            "palette": lambda: manager.create_palette("#0A0E27", "#050811", "#FFFFFF", "#1A1F3A", "#00FFFF", "#FF00FF"),
            "sheet": lambda app: manager._get_file_stylesheet(":/themes/other/NeonButtons.qss", app),
        },
        # Popular VS Code themes - directly integrated with accurate colors from VS Code theme files
        "dracula": {
            "style": "Fusion",
            # Dracula: Popular VS Code theme - vibrant purple, pink, cyan accents on dark purple-gray
            "palette": lambda: manager.create_palette("#282A36", "#21222C", "#F8F8F2", "#343746", "#BD93F9", "#FF79C6"),
        },
        "gruvbox-dark-hard": {
            "style": "Fusion",
            # Gruvbox Dark Hard: Retro groove color scheme - hard contrast variant
            "palette": lambda: manager.create_palette("#1D2021", "#1D2021", "#EBDBB2", "#32302F", "#689D6A", "#FE8019"),
        },
        "gruvbox-dark-medium": {
            "style": "Fusion",
            # Gruvbox Dark Medium: Retro groove color scheme - medium contrast variant
            "palette": lambda: manager.create_palette("#282828", "#282828", "#EBDBB2", "#3C3836", "#689D6A", "#FE8019"),
        },
        "gruvbox-dark-soft": {
            "style": "Fusion",
            # Gruvbox Dark Soft: Retro groove color scheme - soft contrast variant
            "palette": lambda: manager.create_palette("#32302F", "#32302F", "#EBDBB2", "#3C3836", "#689D6A", "#FE8019"),
        },
        "nord": {
            "style": "Fusion",
            # Nord: Arctic, north-bluish color palette
            "palette": lambda: manager.create_palette("#2E3440", "#3B4252", "#E5E9F0", "#434C5E", "#88C0D0", "#ECEFF4"),
        },
        "onedark": {
            "style": "Fusion",
            # One Dark: Popular VS Code theme - Atom's One Dark
            "palette": lambda: manager.create_palette("#282C34", "#21252B", "#ABB2BF", "#3E4451", "#61AFEF", "#FFFFFF"),
        },
        "material-theme-default": {
            "style": "Fusion",
            # Material Theme Default: Google Material Design colors
            "palette": lambda: manager.create_palette("#263238", "#1E1E1E", "#EEFFFF", "#2E2E2E", "#04B97F", "#FFFFFF"),
        },
        "material-theme-darker": {
            "style": "Fusion",
            # Material Theme Darker: Darker variant of Material Theme
            "palette": lambda: manager.create_palette("#212121", "#1E1E1E", "#EEFFFF", "#2E2E2E", "#04B97F", "#FFFFFF"),
        },
        "material-theme-ocean": {
            "style": "Fusion",
            # Material Theme Ocean: Ocean variant with blue accent
            "palette": lambda: manager.create_palette("#263238", "#1E1E1E", "#EEFFFF", "#2E2E2E", "#89DDFF", "#FFFFFF"),
        },
        "material-theme-palenight": {
            "style": "Fusion",
            # Material Theme Palenight: Pale night variant
            "palette": lambda: manager.create_palette("#292D3E", "#1E1E1E", "#EEFFFF", "#3A3F5B", "#82AAFF", "#FFFFFF"),
        },
        "tokyo-night": {
            "style": "Fusion",
            # Tokyo Night: Clean, modern dark theme inspired by Tokyo
            "palette": lambda: manager.create_palette("#1A1B26", "#16161E", "#C0CAF5", "#2F3549", "#7AA2F7", "#BB9AF7"),
        },
        "tokyo-night-storm": {
            "style": "Fusion",
            # Tokyo Night Storm: Darker variant of Tokyo Night
            "palette": lambda: manager.create_palette("#24283B", "#1F2335", "#C0CAF5", "#2F3549", "#7AA2F7", "#BB9AF7"),
        },
        "catppuccin-mocha": {
            "style": "Fusion",
            # Catppuccin Mocha: Soothing pastel theme - mocha variant
            "palette": lambda: manager.create_palette("#1E1E2E", "#11111B", "#CDD6F4", "#313244", "#89B4FA", "#F5C2E7"),
        },
        "catppuccin-frappe": {
            "style": "Fusion",
            # Catppuccin Frappe: Soothing pastel theme - frappe variant
            "palette": lambda: manager.create_palette("#303446", "#232634", "#C6D0F5", "#414559", "#8CAAEE", "#F4B8E4"),
        },
        "github-dark": {
            "style": "Fusion",
            # GitHub Dark: GitHub's official dark theme
            "palette": lambda: manager.create_palette("#0D1117", "#010409", "#C9D1D9", "#161B22", "#58A6FF", "#FFFFFF"),
        },
        "github-dark-dimmed": {
            "style": "Fusion",
            # GitHub Dark Dimmed: Dimmed variant of GitHub Dark
            "palette": lambda: manager.create_palette("#1C2128", "#22272E", "#909DAB", "#373E47", "#6CB6FF", "#FFFFFF"),
        },
        "synthwave-84": {
            "style": "Fusion",
            # Synthwave '84: Retro synthwave aesthetic
            "palette": lambda: manager.create_palette("#262335", "#1A1528", "#FF00FF", "#2D2137", "#F97E72", "#FF6AC1"),
        },
        "night-owl": {
            "style": "Fusion",
            # Night Owl: Optimized for late night coding
            "palette": lambda: manager.create_palette("#011627", "#011627", "#D6DEEB", "#0C2132", "#82AAFF", "#FFE66D"),
        },
        "monokai-pro": {
            "style": "Fusion",
            # Monokai Pro: Professional Monokai variant
            "palette": lambda: manager.create_palette("#2D2A2E", "#221F22", "#FCFCFA", "#403E41", "#FF6188", "#AB9DF2"),
        },
        "ayu-dark": {
            "style": "Fusion",
            # Ayu Dark: Clean, elegant dark theme
            "palette": lambda: manager.create_palette("#1F2430", "#191E2A", "#CBCCC6", "#252936", "#5CCFE6", "#FFCC66"),
        },
        "horizon": {
            "style": "Fusion",
            # Horizon: Warm, dark theme with vibrant colors
            "palette": lambda: manager.create_palette("#1C1E26", "#16161C", "#CECCD0", "#232530", "#26BBD9", "#F43E5C"),
        },
        "rose-pine": {
            "style": "Fusion",
            # Rose Pine: All natural pine, faux fur and a bit of soho vibes
            "palette": lambda: manager.create_palette("#191724", "#13111A", "#E0DEF4", "#1F1D2E", "#EB6F92", "#C4A7E7"),
        },
        "rose-pine-moon": {
            "style": "Fusion",
            # Rose Pine Moon: Moonlight variant
            "palette": lambda: manager.create_palette("#232136", "#1F1D2E", "#E0DEF4", "#2A273F", "#EB6F92", "#C4A7E7"),
        },
        "rose-pine-dawn": {
            "style": "Fusion",
            # Rose Pine Dawn: Dawn variant (light theme)
            "palette": lambda: manager.create_palette("#FAF4ED", "#FFFBF3", "#575279", "#F2EDE9", "#D7827E", "#286983"),
        },
        "everforest": {
            "style": "Fusion",
            # Everforest: Comfortable & Pleasant Color Scheme
            "palette": lambda: manager.create_palette("#2F383E", "#272E33", "#D3C6AA", "#374145", "#A7C080", "#E67E80"),
        },
        "kanagawa": {
            "style": "Fusion",
            # Kanagawa: NeoVim dark theme inspired by Katsushika Hokusai
            "palette": lambda: manager.create_palette("#1F1F28", "#16161D", "#DCD7BA", "#2A2A37", "#7E9CD8", "#C34043"),
        },
        "sonokai": {
            "style": "Fusion",
            # Sonokai: High contrast & vibrant color scheme
            "palette": lambda: manager.create_palette("#2C2E34", "#222426", "#FCFCFA", "#36393E", "#FC9867", "#A9DC76"),
        },
        "vscode-dark": {
            "style": "Fusion",
            # VS Code Dark+: Default VS Code dark theme
            "palette": lambda: manager.create_palette("#1E1E1E", "#252526", "#D4D4D4", "#2D2D30", "#007ACC", "#FFFFFF"),
        },
        "vscode-light": {
            "style": "Fusion",
            # VS Code Light+: Default VS Code light theme
            "palette": lambda: manager.create_palette("#FFFFFF", "#F3F3F3", "#333333", "#F0F0F0", "#007ACC", "#000000"),
        },
        "dark-plus": {
            "style": "Fusion",
            # Dark+: Default VS Code dark theme (alias)
            "palette": lambda: manager.create_palette("#1E1E1E", "#252526", "#D4D4D4", "#2D2D30", "#007ACC", "#FFFFFF"),
        },
        "light-plus": {
            "style": "Fusion",
            # Light+: Default VS Code light theme (alias)
            "palette": lambda: manager.create_palette("#FFFFFF", "#F3F3F3", "#333333", "#F0F0F0", "#007ACC", "#000000"),
        },
        "2077-theme-color-theme": {
            "style": "Fusion",
            # 2077 Theme Color Theme (dark)
            "palette": lambda: manager.create_palette("#030d22", "#030d22", "#ffffff", "#222858", "#310072", "#ffffff"),
        },
        "adapta-nokto": {
            "style": "Fusion",
            # Adapta Nokto (dark)
            "palette": lambda: manager.create_palette("#29353b", "#243035", "#FFFFFF", "#29353b", "#00BCD470", "#FFFFFF"),
        },
        "atelierdune-dark": {
            "style": "Fusion",
            # Atelierdune Dark (dark)
            "palette": lambda: manager.create_palette("#20201D", "#1c1c1a", "#A6A28C", "#1c1c1a", "#6E6B5E", "#FFFFFF"),
        },
        "atelierdune-light": {
            "style": "Fusion",
            # Atelierdune Light (light)
            "palette": lambda: manager.create_palette("#FEFBEC", "#fefbef", "#6E6B5E", "#fefbef", "#E8E4CF", "#FFFFFF"),
        },
        "atelierforest-dark": {
            "style": "Fusion",
            # Atelierforest Dark (dark)
            "palette": lambda: manager.create_palette("#1b1918", "#181615", "#a8a19f", "#181615", "#68615e", "#FFFFFF"),
        },
        "atelierforest-light": {
            "style": "Fusion",
            # Atelierforest Light (light)
            "palette": lambda: manager.create_palette("#F1EFEE", "#f3f2f1", "#68615E", "#f3f2f1", "#E6E2E0", "#FFFFFF"),
        },
        "atelierheath-dark": {
            "style": "Fusion",
            # Atelierheath Dark (dark)
            "palette": lambda: manager.create_palette("#1b181b", "#181518", "#ab9bab", "#181518", "#695d69", "#FFFFFF"),
        },
        "atelierheath-light": {
            "style": "Fusion",
            # Atelierheath Light (light)
            "palette": lambda: manager.create_palette("#f7f3f7", "#f8f5f8", "#695d69", "#f8f5f8", "#d8cad8", "#FFFFFF"),
        },
        "atelierlakeside-dark": {
            "style": "Fusion",
            # Atelierlakeside Dark (dark)
            "palette": lambda: manager.create_palette("#161b1d", "#13181a", "#7ea2b4", "#13181a", "#516d7b", "#FFFFFF"),
        },
        "atelierlakeside-light": {
            "style": "Fusion",
            # Atelierlakeside Light (light)
            "palette": lambda: manager.create_palette("#ebf8ff", "#eff9ff", "#516d7b", "#eff9ff", "#c1e4f6", "#FFFFFF"),
        },
        "atelierseaside-dark": {
            "style": "Fusion",
            # Atelierseaside Dark (dark)
            "palette": lambda: manager.create_palette("#131513", "#111211", "#8ca68c", "#111211", "#5e6e5e", "#FFFFFF"),
        },
        "atelierseaside-light": {
            "style": "Fusion",
            # Atelierseaside Light (light)
            "palette": lambda: manager.create_palette("#f0fff0", "#f3fff3", "#5e6e5e", "#f3fff3", "#cfe8cf", "#FFFFFF"),
        },
        "aurora-x-color-theme": {
            "style": "Fusion",
            # Aurora X Color Theme (dark)
            "palette": lambda: manager.create_palette("#07090F", "#07090F", "#576daf", "#15182B", "#262E47", "#576daf"),
        },
        "catrina-dark-color-theme": {
            "style": "Fusion",
            # Catrina Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#0d0015", "#160517", "#9ebdd3", "#210e00", "#b07caa40", "#9ebdd3"),
        },
        "cpptools_dark_vs": {
            "style": "Fusion",
            # Cpptools Dark Vs (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#D4D4D4", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "cpptools_dark_vs_new": {
            "style": "Fusion",
            # Cpptools Dark Vs New (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#DADADA", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "cpptools_light_vs_new": {
            "style": "Fusion",
            # Cpptools Light Vs New (dark)
            "palette": lambda: manager.create_palette("#FFFFFF", "#FFFFFF", "#000000", "#FFFFFF", "#0078D4", "#FFFFFF"),
        },
        "cyberpunk-color-theme": {
            "style": "Fusion",
            # Cyberpunk Color Theme (dark)
            "palette": lambda: manager.create_palette("#261D45", "#372963", "#ffffff", "#002212ec", "#311b92", "#ffffff"),
        },
        "cyberpunk-scarlet-color-theme": {
            "style": "Fusion",
            # Cyberpunk Scarlet Color Theme (dark)
            "palette": lambda: manager.create_palette("#101116", "#0a0b0e", "#ffffff", "#140007f8", "#000000", "#ffffff"),
        },
        "deep-purple-color-theme": {
            "style": "Fusion",
            # Deep Purple Color Theme (dark)
            "palette": lambda: manager.create_palette("#17002f", "#17002f", "#dfafff", "#1f003f", "#3f007f", "#dfafff"),
        },
        "default": {
            "style": "Fusion",
            # Default (dark)
            "palette": lambda: manager.create_palette("#1f1f1f", "#161616", "#dddddd", "#363636", "#464646", "#dddddd"),
        },
        "electron-color-theme": {
            "style": "Fusion",
            # Electron Color Theme (dark)
            "palette": lambda: manager.create_palette("#212836", "#1C212E", "#818CA6", "#141820", "#e6eeff21", "#818CA6"),
        },
        "ghostish-color-theme": {
            "style": "Fusion",
            # Ghostish Color Theme (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#c4c4c4", "#000000", "#c4c4c440", "#c4c4c4"),
        },
        "github-plus-theme": {
            "style": "Fusion",
            # Github Plus Theme (light)
            "palette": lambda: manager.create_palette("#ffffff", "#fafbfc", "#24292e", "#fafbfc", "#fafbfc", "#FFFFFF"),
        },
        "green-abyss-color-theme": {
            "style": "Fusion",
            # Green Abyss Color Theme (dark)
            "palette": lambda: manager.create_palette("#00180c", "#062106", "#9dcaac", "#12411ce8", "#6b917c70", "#FFFFFF"),
        },
        "gruvbox-dark-hard2": {
            "style": "Fusion",
            # Gruvbox Dark Hard (dark)
            "palette": lambda: manager.create_palette("#1d2021", "#1d2021", "#ebdbb2", "#1d2021", "#689d6a40", "#ebdbb2"),
        },
        "gruvbox-dark-medium2": {
            "style": "Fusion",
            # Gruvbox Dark Medium (dark)
            "palette": lambda: manager.create_palette("#282828", "#282828", "#ebdbb2", "#282828", "#689d6a40", "#ebdbb2"),
        },
        "gruvbox-dark-soft2": {
            "style": "Fusion",
            # Gruvbox Dark Soft (dark)
            "palette": lambda: manager.create_palette("#32302f", "#32302f", "#ebdbb2", "#32302f", "#689d6a40", "#ebdbb2"),
        },
        "gruvbox-light-hard": {
            "style": "Fusion",
            # Gruvbox Light Hard (dark)
            "palette": lambda: manager.create_palette("#f9f5d7", "#f9f5d7", "#3c3836", "#f9f5d7", "#689d6a40", "#3c3836"),
        },
        "gruvbox-light-medium": {
            "style": "Fusion",
            # Gruvbox Light Medium (dark)
            "palette": lambda: manager.create_palette("#fbf1c7", "#fbf1c7", "#3c3836", "#fbf1c7", "#689d6a40", "#3c3836"),
        },
        "gruvbox-light-soft": {
            "style": "Fusion",
            # Gruvbox Light Soft (dark)
            "palette": lambda: manager.create_palette("#f2e5bc", "#f2e5bc", "#3c3836", "#f2e5bc", "#689d6a40", "#3c3836"),
        },
        "hackthebox-lite": {
            "style": "Fusion",
            # Hackthebox Lite (dark)
            "palette": lambda: manager.create_palette("#1a2332", "#1a2332", "#a4b1cd", "#1a2332", "#313f55", "#a4b1cd"),
        },
        "hackthebox": {
            "style": "Fusion",
            # Hackthebox (dark)
            "palette": lambda: manager.create_palette("#141d2b", "#1a2332", "#a4b1cd", "#1a2332", "#6e7b968C", "#a4b1cd"),
        },
        "halcyon-color-theme": {
            "style": "Fusion",
            # Halcyon Color Theme (dark)
            "palette": lambda: manager.create_palette("#1d2433", "#171c28", "#8695b7", "#2f3b54", "#2f3b54", "#8695b7"),
        },
        "lightanian-tokyo-night": {
            "style": "Fusion",
            # Lightanian Tokyo Night (light)
            "palette": lambda: manager.create_palette("#e6e7ed", "#d6d8df", "#363c4d", "#dcdee3", "#acb0bf40", "#363c4d"),
        },
        "material-theme-oled-color-theme": {
            "style": "Fusion",
            # Material Theme Oled Color Theme (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#eeffff", "#000000", "#61616150", "#eeffff"),
        },
        "narutovisk-color-theme": {
            "style": "Fusion",
            # Narutovisk Color Theme (dark)
            "palette": lambda: manager.create_palette("#0d0d1d", "#070416", "#ffffff", "#070416", "#0078D4", "#FFFFFF"),
        },
        "night-owl-light-color-theme": {
            "style": "Fusion",
            # Night Owl Light Color Theme (light)
            "palette": lambda: manager.create_palette("#FBFBFB", "#F0F0F0", "#403f53", "#F0F0F0", "#E0E0E0", "#403f53"),
        },
        "pink-theme-color-theme": {
            "style": "Fusion",
            # Pink Theme Color Theme (dark)
            "palette": lambda: manager.create_palette("#3c0734", "#581041", "#f1efef", "#6b184b", "#810b7f", "#f1efef"),
        },
        "shades-of-purple-color-theme-italic": {
            "style": "Fusion",
            # Shades Of Purple Color Theme Italic (dark)
            "palette": lambda: manager.create_palette("#2D2B55", "#222244", "#A599E9", "#1F1F41", "#B362FF88", "#A599E9"),
        },
        "shades-of-purple-color-theme-super-dark": {
            "style": "Fusion",
            # Shades Of Purple Color Theme Super Dark (dark)
            "palette": lambda: manager.create_palette("#191830", "#131327", "#A599E9", "#161633", "#5706a288", "#A599E9"),
        },
        "shades-of-purple-color-theme": {
            "style": "Fusion",
            # Shades Of Purple Color Theme (dark)
            "palette": lambda: manager.create_palette("#2D2B55", "#222244", "#A599E9", "#161633", "#B362FF88", "#A599E9"),
        },
        "skgrtt-theme-color-theme": {
            "style": "Fusion",
            # Skgrtt Theme Color Theme (dark)
            "palette": lambda: manager.create_palette("#140101", "#1d0101", "#bbbbbb", "#300000", "#690404", "#FFFFFF"),
        },
        "solarized-dark-color-theme": {
            "style": "Fusion",
            # Solarized Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#002b36", "#001f26", "#93a1a1", "#001f26", "#268ad25b", "#93a1a1"),
        },
        "solarized-dark-high-contrast-color-theme": {
            "style": "Fusion",
            # Solarized Dark High Contrast Color Theme (dark)
            "palette": lambda: manager.create_palette("#002b36", "#001f26", "#93a1a1", "#001f26", "#268ad25b", "#93a1a1"),
        },
        "solarized-light-color-theme": {
            "style": "Fusion",
            # Solarized Light Color Theme (dark)
            "palette": lambda: manager.create_palette("#fdf6e3", "#00212b", "#657b83", "#004052", "#274642", "#FFFFFF"),
        },
        "sourcegraph-dark": {
            "style": "Fusion",
            # Sourcegraph Dark (dark)
            "palette": lambda: manager.create_palette("#0E121B", "#1D2535", "#F2F4F8", "#1D2535", "#1C7CD650", "#F2F4F8"),
        },
        "sublime-monokai-color-theme": {
            "style": "Fusion",
            # Sublime Monokai Color Theme (dark)
            "palette": lambda: manager.create_palette("#272822", "#1e1f1c", "#f8f8f2", "#414339", "#878b9180", "#FFFFFF"),
        },
        "tokyo-darker-night-color-theme": {
            "style": "Fusion",
            # Tokyo Darker Night Color Theme (dark)
            "palette": lambda: manager.create_palette("#0e0e0e", "#0e0e0e", "#D5D8DA", "#141414", "#a42aeb3d", "#D5D8DA"),
        },
        "ui-key-tester": {
            "style": "Fusion",
            # Ui Key Tester (dark)
            "palette": lambda: manager.create_palette("#FF0000", "#FF0000", "#FF0000", "#FF0000", "#FF0000", "#FF0000"),
        },
        "vs2019_light": {
            "style": "Fusion",
            # Vs2019 Light (light)
            "palette": lambda: manager.create_palette("#FFFFFF", "#FFFFFF", "#000000", "#FFFFFF", "#0078D4", "#FFFFFF"),
        },
        "winteriscoming-dark-blue-color-no-italics-theme": {
            "style": "Fusion",
            # Winteriscoming Dark Blue Color No Italics Theme (dark)
            "palette": lambda: manager.create_palette("#011627", "#011627", "#d6deeb", "#011627", "#103362", "#d6deeb"),
        },
        "xcode-big-sur": {
            "style": "Fusion",
            # Xcode Big Sur (light)
            "palette": lambda: manager.create_palette("#ffffff", "#f8f8f7", "#434343", "#f2f2f2", "#b5d5ff", "#434343"),
        },
        "xcode-default-dark": {
            "style": "Fusion",
            # Xcode Default Dark (dark)
            "palette": lambda: manager.create_palette("#232222", "#353333", "#a3a2a2", "#2c2c2b", "#6e6e6e", "#a3a2a2"),
        },
        "xcode-default": {
            "style": "Fusion",
            # Xcode Default (light)
            "palette": lambda: manager.create_palette("#ffffff", "#f8f8f7", "#434343", "#f2f2f2", "#b5d5ff", "#434343"),
        },
        "xcode-low-key": {
            "style": "Fusion",
            # Xcode Low Key (light)
            "palette": lambda: manager.create_palette("#ffffff", "#f8f8f7", "#434343", "#f8f8f7", "#b5d5ff", "#434343"),
        },
        "xcode-modern": {
            "style": "Fusion",
            # Xcode Modern (dark)
            "palette": lambda: manager.create_palette("#242529", "#303136", "#ffffff", "#303136", "#444444", "#ffffff"),
        },
        "xcode-ventura": {
            "style": "Fusion",
            # Xcode Ventura (dark)
            "palette": lambda: manager.create_palette("#232222", "#353333", "#a3a2a2", "#2c2c2b", "#6e6e6e", "#a3a2a2"),
        },
        "yarra-valley": {
            "style": "Fusion",
            # Yarra Valley (dark)
            "palette": lambda: manager.create_palette("#292d3e", "#242837", "#e3d8be", "#3e4251", "#474e6c", "#e3d8be"),
        },
        "3024-dark": {
            "style": "Fusion",
            # 3024 Dark (dark)
            "palette": lambda: manager.create_palette("#090300", "#3a3432", "#a5a2a2", "#090300", "#4a4543", "#a5a2a2"),
        },
        "3024-light": {
            "style": "Fusion",
            # 3024 Light (light)
            "palette": lambda: manager.create_palette("#f7f7f7", "#d6d5d4", "#4a4543", "#f7f7f7", "#a5a2a2", "#4a4543"),
        },
        "ambiance": {
            "style": "Fusion",
            # Ambiance (dark)
            "palette": lambda: manager.create_palette("#31312e", "#373633", "#dddddd", "#373633", "#e0dedc20", "#FFFFFF"),
        },
        "andromeda-color-theme-bordered": {
            "style": "Fusion",
            # Andromeda Color Theme Bordered (dark)
            "palette": lambda: manager.create_palette("#262A33", "#23262E", "#D5CED9", "#373941", "#3D4352", "#D5CED9"),
        },
        "andromeda-color-theme": {
            "style": "Fusion",
            # Andromeda Color Theme (dark)
            "palette": lambda: manager.create_palette("#23262E", "#23262E", "#D5CED9", "#373941", "#3D4352", "#D5CED9"),
        },
        "andromeda-italic-color-theme-bordered": {
            "style": "Fusion",
            # Andromeda Italic Color Theme Bordered (dark)
            "palette": lambda: manager.create_palette("#262A33", "#23262E", "#D5CED9", "#373941", "#3D4352", "#D5CED9"),
        },
        "andromeda-italic-color-theme": {
            "style": "Fusion",
            # Andromeda Italic Color Theme (dark)
            "palette": lambda: manager.create_palette("#23262E", "#23262E", "#D5CED9", "#373941", "#3D4352", "#D5CED9"),
        },
        "apathy-dark": {
            "style": "Fusion",
            # Apathy Dark (dark)
            "palette": lambda: manager.create_palette("#031A16", "#0B342D", "#81B5AC", "#031A16", "#184E45", "#81B5AC"),
        },
        "apathy-light": {
            "style": "Fusion",
            # Apathy Light (light)
            "palette": lambda: manager.create_palette("#D2E7E4", "#A7CEC8", "#184E45", "#D2E7E4", "#81B5AC", "#184E45"),
        },
        "aqua-theme": {
            "style": "Fusion",
            # Aqua Theme (dark)
            "palette": lambda: manager.create_palette("#262940", "#262940", "#bbbbbb", "#2a2d44", "#4C637A66", "#bbbbbb"),
        },
        "arc-dark": {
            "style": "Fusion",
            # Arc Dark (dark)
            "palette": lambda: manager.create_palette("#2f343f", "#262b33", "#D3DAE3", "#2f343f", "#88F5", "#D3DAE3"),
        },
        "ashes-dark": {
            "style": "Fusion",
            # Ashes Dark (dark)
            "palette": lambda: manager.create_palette("#1C2023", "#393F45", "#C7CCD1", "#1C2023", "#565E65", "#C7CCD1"),
        },
        "ashes-light": {
            "style": "Fusion",
            # Ashes Light (light)
            "palette": lambda: manager.create_palette("#F3F4F5", "#DFE2E5", "#565E65", "#F3F4F5", "#C7CCD1", "#565E65"),
        },
        "astolfo-theme": {
            "style": "Fusion",
            # Astolfo Theme (dark)
            "palette": lambda: manager.create_palette("#1a1c19", "#1a1c19", "#bbbbbb", "#181917", "#501C1C", "#bbbbbb"),
        },
        "asuna-dark-theme": {
            "style": "Fusion",
            # Asuna Dark Theme (dark)
            "palette": lambda: manager.create_palette("#1b1b1b", "#1b1b1b", "#bbbbbb", "#1e1e1e", "#531616", "#bbbbbb"),
        },
        "asuna-light-theme": {
            "style": "Fusion",
            # Asuna Light Theme (light)
            "palette": lambda: manager.create_palette("#fcfcfc", "#fcfcfc", "#252427", "#fdfdfd", "#e9b4b855", "#252427"),
        },
        "aura-dark-color-theme": {
            "style": "Fusion",
            # Aura Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#15141b", "#110f18", "#edecee", "#121016", "#3d375e7f", "#edecee"),
        },
        "aura-dark-soft-text-color-theme": {
            "style": "Fusion",
            # Aura Dark Soft Text Color Theme (dark)
            "palette": lambda: manager.create_palette("#15141b", "#110f18", "#bdbdbd", "#121016", "#3d375e7f", "#bdbdbd"),
        },
        "aura-soft-dark-color-theme": {
            "style": "Fusion",
            # Aura Soft Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#21202e", "#1c1b22", "#edecee", "#1f1a27", "#3d375e7f", "#edecee"),
        },
        "aura-soft-dark-soft-text-color-theme": {
            "style": "Fusion",
            # Aura Soft Dark Soft Text Color Theme (dark)
            "palette": lambda: manager.create_palette("#21202e", "#1c1b22", "#bdbdbd", "#1f1a27", "#3d375e7f", "#bdbdbd"),
        },
        "azuki-theme": {
            "style": "Fusion",
            # Azuki Theme (dark)
            "palette": lambda: manager.create_palette("#2e221f", "#2e221f", "#bfbfbf", "#2d221f", "#684e29AA", "#bfbfbf"),
        },
        "bearded-theme-altica": {
            "style": "Fusion",
            # Bearded Theme Altica (dark)
            "palette": lambda: manager.create_palette("#0f1c21", "#0e171c", "#9FADB1", "#15262e", "#0187a64d", "#9FADB1"),
        },
        "bearded-theme-aquarelle-cymbidium": {
            "style": "Fusion",
            # Bearded Theme Aquarelle Cymbidium (dark)
            "palette": lambda: manager.create_palette("#2c252a", "#262024", "#c6bdc4", "#3a3137", "#da6e6c4d", "#c6bdc4"),
        },
        "bearded-theme-aquarelle-hydrangea": {
            "style": "Fusion",
            # Bearded Theme Aquarelle Hydrangea (dark)
            "palette": lambda: manager.create_palette("#22273c", "#1e2235", "#b9bfd7", "#2b324c", "#6394f14d", "#b9bfd7"),
        },
        "bearded-theme-aquarelle-lilac": {
            "style": "Fusion",
            # Bearded Theme Aquarelle Lilac (dark)
            "palette": lambda: manager.create_palette("#252433", "#201f2c", "#bcbbce", "#302f42", "#9587ff4d", "#bcbbce"),
        },
        "bearded-theme-aquerelle-hydrangea": {
            "style": "Fusion",
            # Bearded Theme Aquerelle Hydrangea (dark)
            "palette": lambda: manager.create_palette("#23293b", "#1f2434", "#bfc4d1AA", "#2c344b", "#4c86f14d", "#bfc4d1AA"),
        },
        "bearded-theme-arc-blueberry": {
            "style": "Fusion",
            # Bearded Theme Arc Blueberry (dark)
            "palette": lambda: manager.create_palette("#111422", "#0d101b", "#9aa2cb", "#1a1e33", "#8eb0e64d", "#9aa2cb"),
        },
        "bearded-theme-arc-eggplant": {
            "style": "Fusion",
            # Bearded Theme Arc Eggplant (dark)
            "palette": lambda: manager.create_palette("#181421", "#13101a", "#ada2c5", "#241e31", "#9698d84d", "#ada2c5"),
        },
        "bearded-theme-arc-eolstorm": {
            "style": "Fusion",
            # Bearded Theme Arc Eolstorm (dark)
            "palette": lambda: manager.create_palette("#222A38", "#1e2531", "#b9c2d3", "#2c3648", "#9dacc34d", "#b9c2d3"),
        },
        "bearded-theme-arc-reversed": {
            "style": "Fusion",
            # Bearded Theme Arc Reversed (dark)
            "palette": lambda: manager.create_palette("#121721", "#161c28", "#a4b1cc", "#1f2838", "#8196b54d", "#a4b1cc"),
        },
        "bearded-theme-arc": {
            "style": "Fusion",
            # Bearded Theme Arc (dark)
            "palette": lambda: manager.create_palette("#1c2433", "#181f2c", "#afbbd2", "#253043", "#8196b54d", "#afbbd2"),
        },
        "bearded-theme-black-amethyst-soft": {
            "style": "Fusion",
            # Bearded Theme Black Amethyst Soft (dark)
            "palette": lambda: manager.create_palette("#171626", "#13121f", "#a7a5c9", "#211f36", "#a85ff14d", "#a7a5c9"),
        },
        "bearded-theme-black-amethyst": {
            "style": "Fusion",
            # Bearded Theme Black Amethyst (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a0acbb", "#1c2027", "#a85ff14d", "#a0acbb"),
        },
        "bearded-theme-black-diamond-soft": {
            "style": "Fusion",
            # Bearded Theme Black Diamond Soft (dark)
            "palette": lambda: manager.create_palette("#161d26", "#12181f", "#a5b5c9", "#1f2936", "#11b7d44d", "#a5b5c9"),
        },
        "bearded-theme-black-diamond": {
            "style": "Fusion",
            # Bearded Theme Black Diamond (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a0acbb", "#1c2027", "#11b7d44d", "#a0acbb"),
        },
        "bearded-theme-black-emerald-soft": {
            "style": "Fusion",
            # Bearded Theme Black Emerald Soft (dark)
            "palette": lambda: manager.create_palette("#162226", "#121c1f", "#a5c0c9", "#1f3036", "#38c7bd4d", "#a5c0c9"),
        },
        "bearded-theme-black-emerald": {
            "style": "Fusion",
            # Bearded Theme Black Emerald (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a0acbb", "#1c2027", "#38c7bd4d", "#a0acbb"),
        },
        "bearded-theme-black-gold-soft": {
            "style": "Fusion",
            # Bearded Theme Black Gold Soft (dark)
            "palette": lambda: manager.create_palette("#221f1d", "#1c1918", "#bdb8b4", "#302c29", "#c7910c4d", "#bdb8b4"),
        },
        "bearded-theme-black-gold": {
            "style": "Fusion",
            # Bearded Theme Black Gold (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a0acbb", "#1c2027", "#c7910c4d", "#a0acbb"),
        },
        "bearded-theme-black-ruby-soft": {
            "style": "Fusion",
            # Bearded Theme Black Ruby Soft (dark)
            "palette": lambda: manager.create_palette("#281a21", "#21161b", "#c8acba", "#37242e", "#c62f524d", "#c8acba"),
        },
        "bearded-theme-black-ruby": {
            "style": "Fusion",
            # Bearded Theme Black Ruby (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a0acbb", "#1c2027", "#c62f524d", "#a0acbb"),
        },
        "bearded-theme-black-amethyst-soft2": {
            "style": "Fusion",
            # Bearded Theme Black Amethyst Soft (dark)
            "palette": lambda: manager.create_palette("#171626", "#13121f", "#acabc3AA", "#211f36", "#a85ff140", "#acabc3AA"),
        },
        "bearded-theme-black-amethyst2": {
            "style": "Fusion",
            # Bearded Theme Black Amethyst (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a8adb3AA", "#1c2027", "#a85ff140", "#a8adb3AA"),
        },
        "bearded-theme-black-diamond-soft2": {
            "style": "Fusion",
            # Bearded Theme Black Diamond Soft (dark)
            "palette": lambda: manager.create_palette("#161d26", "#12181f", "#abb6c3AA", "#1f2936", "#11b7d440", "#abb6c3AA"),
        },
        "bearded-theme-black-diamond2": {
            "style": "Fusion",
            # Bearded Theme Black Diamond (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a8adb3AA", "#1c2027", "#11b7d440", "#a8adb3AA"),
        },
        "bearded-theme-black-emerald-soft2": {
            "style": "Fusion",
            # Bearded Theme Black Emerald Soft (dark)
            "palette": lambda: manager.create_palette("#162226", "#121c1f", "#abbdc3AA", "#1f3036", "#38c7bd40", "#abbdc3AA"),
        },
        "bearded-theme-black-emerald2": {
            "style": "Fusion",
            # Bearded Theme Black Emerald (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a8adb3AA", "#1c2027", "#38c7bd40", "#a8adb3AA"),
        },
        "bearded-theme-black-gold-soft2": {
            "style": "Fusion",
            # Bearded Theme Black Gold Soft (dark)
            "palette": lambda: manager.create_palette("#221f1d", "#1c1918", "#b8b8b8AA", "#302c29", "#c7910c40", "#b8b8b8AA"),
        },
        "bearded-theme-black-gold2": {
            "style": "Fusion",
            # Bearded Theme Black Gold (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a8adb3AA", "#1c2027", "#c7910c40", "#a8adb3AA"),
        },
        "bearded-theme-black-ruby-soft2": {
            "style": "Fusion",
            # Bearded Theme Black Ruby Soft (dark)
            "palette": lambda: manager.create_palette("#281a21", "#21161b", "#c2b2baAA", "#37242e", "#c62f5240", "#c2b2baAA"),
        },
        "bearded-theme-black-ruby2": {
            "style": "Fusion",
            # Bearded Theme Black Ruby (dark)
            "palette": lambda: manager.create_palette("#111418", "#0c0f11", "#a8adb3AA", "#1c2027", "#c62f5240", "#a8adb3AA"),
        },
        "bearded-theme-classics-anthracite": {
            "style": "Fusion",
            # Bearded Theme Classics Anthracite (dark)
            "palette": lambda: manager.create_palette("#181a1f", "#131519", "#acb1bd", "#23262d", "#a2abb64d", "#acb1bd"),
        },
        "bearded-theme-classics-light": {
            "style": "Fusion",
            # Bearded Theme Classics Light (dark)
            "palette": lambda: manager.create_palette("#f3f4f5", "#e9ebed", "#000000", "#f9f9fa", "#52c1da4d", "#000000"),
        },
        "bearded-theme-coffee-cream": {
            "style": "Fusion",
            # Bearded Theme Coffee Cream (dark)
            "palette": lambda: manager.create_palette("#EAE4E1", "#e3dbd7", "#000000", "#eee9e7", "#d3694c4d", "#000000"),
        },
        "bearded-theme-coffee-reversed": {
            "style": "Fusion",
            # Bearded Theme Coffee Reversed (dark)
            "palette": lambda: manager.create_palette("#1a1716", "#201c1b", "#b7a29d", "#51403b", "#f091774d", "#b7a29d"),
        },
        "bearded-theme-coffee": {
            "style": "Fusion",
            # Bearded Theme Coffee (dark)
            "palette": lambda: manager.create_palette("#292423", "#231f1e", "#beaba7", "#51403b", "#f091774d", "#beaba7"),
        },
        "bearded-theme-earth": {
            "style": "Fusion",
            # Bearded Theme Earth (dark)
            "palette": lambda: manager.create_palette("#221b1b", "#1c1616", "#ba9b9b", "#40222e", "#d353864d", "#ba9b9b"),
        },
        "bearded-theme-feat-gold-d-raynh-light": {
            "style": "Fusion",
            # Bearded Theme Feat Gold D Raynh Light (dark)
            "palette": lambda: manager.create_palette("#f5f5f5", "#ececec", "#000000", "#fafafa", "#2397e54d", "#000000"),
        },
        "bearded-theme-feat-gold-d-raynh": {
            "style": "Fusion",
            # Bearded Theme Feat Gold D Raynh (dark)
            "palette": lambda: manager.create_palette("#0f1628", "#0c1220", "#93a6d6", "#16203b", "#39539780", "#93a6d6"),
        },
        "bearded-theme-feat-mellejulie-light": {
            "style": "Fusion",
            # Bearded Theme Feat Mellejulie Light (dark)
            "palette": lambda: manager.create_palette("#edeeee", "#e4e5e5", "#000000", "#f2f3f3", "#218d8f4d", "#000000"),
        },
        "bearded-theme-feat-mellejulie": {
            "style": "Fusion",
            # Bearded Theme Feat Mellejulie (dark)
            "palette": lambda: manager.create_palette("#1c1f24", "#171a1e", "#b1b7c1", "#272b32", "#63edef4d", "#b1b7c1"),
        },
        "bearded-theme-feat-webdevcody": {
            "style": "Fusion",
            # Bearded Theme Feat Webdevcody (dark)
            "palette": lambda: manager.create_palette("#00171a", "#000d0f", "#4eeafe", "#104c52", "#009eb380", "#4eeafe"),
        },
        "bearded-theme-feat-will": {
            "style": "Fusion",
            # Bearded Theme Feat Will (dark)
            "palette": lambda: manager.create_palette("#14111f", "#0d0a14", "#bfb9da", "#231e36", "#54478280", "#bfb9da"),
        },
        "bearded-theme-hc-brewing-storm": {
            "style": "Fusion",
            # Bearded Theme Hc Brewing Storm (dark)
            "palette": lambda: manager.create_palette("#0c2a42", "#0a2439", "#95c5eb", "#2a5a5c", "#9dffd94d", "#95c5eb"),
        },
        "bearded-theme-hc-chocolate-espresso": {
            "style": "Fusion",
            # Bearded Theme Hc Chocolate Espresso (dark)
            "palette": lambda: manager.create_palette("#2e2424", "#281f1f", "#c3a7a7", "#5d423d", "#f69c954d", "#c3a7a7"),
        },
        "bearded-theme-hc-ebony": {
            "style": "Fusion",
            # Bearded Theme Hc Ebony (dark)
            "palette": lambda: manager.create_palette("#181820", "#13131a", "#ababbf", "#23232f", "#dbdeea4d", "#ababbf"),
        },
        "bearded-theme-hc-flurry": {
            "style": "Fusion",
            # Bearded Theme Hc Flurry (dark)
            "palette": lambda: manager.create_palette("#f5f8fc", "#EAECEE", "#3f4750", "#f9fbfe", "#444c544d", "#3f4750"),
        },
        "bearded-theme-hc-midnightvoid": {
            "style": "Fusion",
            # Bearded Theme Hc Midnightvoid (dark)
            "palette": lambda: manager.create_palette("#151f27", "#111920", "#a2b9cc", "#1e2c38", "#dbefff4d", "#a2b9cc"),
        },
        "bearded-theme-hc-minuit": {
            "style": "Fusion",
            # Bearded Theme Hc Minuit (dark)
            "palette": lambda: manager.create_palette("#1C1827", "#171420", "#b1a8c9", "#635345", "#ecc48c4d", "#b1a8c9"),
        },
        "bearded-theme-hc-wonderland-wood": {
            "style": "Fusion",
            # Bearded Theme Hc Wonderland Wood (dark)
            "palette": lambda: manager.create_palette("#1F1D36", "#1b192f", "#b4b1d4", "#52426a", "#fbe7c34d", "#b4b1d4"),
        },
        "bearded-theme-milkshake-blueberry": {
            "style": "Fusion",
            # Bearded Theme Milkshake Blueberry (dark)
            "palette": lambda: manager.create_palette("#dad9eb", "#cfcde5", "#000000", "#e1e0ef", "#422eb04d", "#000000"),
        },
        "bearded-theme-milkshake-mango": {
            "style": "Fusion",
            # Bearded Theme Milkshake Mango (dark)
            "palette": lambda: manager.create_palette("#f3eae3", "#eee1d7", "#000000", "#f6efea", "#bd4f274d", "#000000"),
        },
        "bearded-theme-milkshake-mint": {
            "style": "Fusion",
            # Bearded Theme Milkshake Mint (dark)
            "palette": lambda: manager.create_palette("#edf3ee", "#e2ece4", "#000000", "#f3f7f4", "#2a9b7d4d", "#000000"),
        },
        "bearded-theme-milkshake-raspberry": {
            "style": "Fusion",
            # Bearded Theme Milkshake Raspberry (dark)
            "palette": lambda: manager.create_palette("#f1e8eb", "#eadde1", "#000000", "#f6eff1", "#d1174f4d", "#000000"),
        },
        "bearded-theme-milkshake-vanilla": {
            "style": "Fusion",
            # Bearded Theme Milkshake Vanilla (dark)
            "palette": lambda: manager.create_palette("#ece7da", "#e6dfce", "#000000", "#efebe1", "#9374164d", "#000000"),
        },
        "bearded-theme-monokai-black": {
            "style": "Fusion",
            # Bearded Theme Monokai Black (dark)
            "palette": lambda: manager.create_palette("#141414", "#0e0e0e", "#adadad", "#212121", "#8f8f8f4d", "#adadad"),
        },
        "bearded-theme-monokai-metallian": {
            "style": "Fusion",
            # Bearded Theme Monokai Metallian (dark)
            "palette": lambda: manager.create_palette("#1e212b", "#191c24", "#b2b8c9", "#282d3a", "#98a2b54d", "#b2b8c9"),
        },
        "bearded-theme-monokai-reversed": {
            "style": "Fusion",
            # Bearded Theme Monokai Reversed (dark)
            "palette": lambda: manager.create_palette("#12141a", "#171921", "#a9aec1", "#212430", "#98a2b54d", "#a9aec1"),
        },
        "bearded-theme-monokai-stone": {
            "style": "Fusion",
            # Bearded Theme Monokai Stone (dark)
            "palette": lambda: manager.create_palette("#2A2D33", "#25282d", "#c3c6cc", "#363941", "#9aa2a64d", "#c3c6cc"),
        },
        "bearded-theme-monokai-terra": {
            "style": "Fusion",
            # Bearded Theme Monokai Terra (dark)
            "palette": lambda: manager.create_palette("#262329", "#201e23", "#bfbbc3", "#332f37", "#b0a2a64d", "#bfbbc3"),
        },
        "bearded-theme-oceanic-reversed": {
            "style": "Fusion",
            # Bearded Theme Oceanic Reversed (dark)
            "palette": lambda: manager.create_palette("#111c22", "#152229", "#a2bfce", "#1e303a", "#97c8924d", "#a2bfce"),
        },
        "bearded-theme-oceanic": {
            "style": "Fusion",
            # Bearded Theme Oceanic (dark)
            "palette": lambda: manager.create_palette("#1a2b34", "#16252d", "#acc6d4", "#284450", "#97c8924d", "#acc6d4"),
        },
        "bearded-theme-solarized-light": {
            "style": "Fusion",
            # Bearded Theme Solarized Light (dark)
            "palette": lambda: manager.create_palette("#fdf6e3", "#f4edda", "#000000", "#fef9ed", "#2aa1984d", "#000000"),
        },
        "bearded-theme-solarized-reversed": {
            "style": "Fusion",
            # Bearded Theme Solarized Reversed (dark)
            "palette": lambda: manager.create_palette("#0d1a20", "#102128", "#96c2d4", "#17303a", "#47cfc44d", "#96c2d4"),
        },
        "bearded-theme-stained-blue": {
            "style": "Fusion",
            # Bearded Theme Stained Blue (dark)
            "palette": lambda: manager.create_palette("#121726", "#0e121e", "#9ba8cf", "#1a2137", "#3a7fff4d", "#9ba8cf"),
        },
        "bearded-theme-stained-purple": {
            "style": "Fusion",
            # Bearded Theme Stained Purple (dark)
            "palette": lambda: manager.create_palette("#20192b", "#1b1524", "#b7aacc", "#2c223b", "#a948ef4d", "#b7aacc"),
        },
        "bearded-theme-surprising-blueberry": {
            "style": "Fusion",
            # Bearded Theme Surprising Blueberry (dark)
            "palette": lambda: manager.create_palette("#101a29", "#0d1521", "#96afd5", "#441f30", "#c93e714d", "#96afd5"),
        },
        "bearded-theme-surprising-eggplant": {
            "style": "Fusion",
            # Bearded Theme Surprising Eggplant (dark)
            "palette": lambda: manager.create_palette("#1d1426", "#17101f", "#b6a0cc", "#441f30", "#d24e4e4d", "#b6a0cc"),
        },
        "bearded-theme-surprising-watermelon": {
            "style": "Fusion",
            # Bearded Theme Surprising Watermelon (dark)
            "palette": lambda: manager.create_palette("#142326", "#101c1f", "#a0c5cc", "#5f3333", "#da6c624d", "#a0c5cc"),
        },
        "bearded-theme-themanopia": {
            "style": "Fusion",
            # Bearded Theme Themanopia (dark)
            "palette": lambda: manager.create_palette("#1b1e28", "#161921", "#aeb4c7", "#252937", "#9887eb4d", "#aeb4c7"),
        },
        "bearded-theme-vivid-black": {
            "style": "Fusion",
            # Bearded Theme Vivid Black (dark)
            "palette": lambda: manager.create_palette("#141417", "#0f0f11", "#aaaab3", "#202025", "#aaaaaa4d", "#aaaab3"),
        },
        "bearded-theme-vivid-light": {
            "style": "Fusion",
            # Bearded Theme Vivid Light (dark)
            "palette": lambda: manager.create_palette("#f4f4f4", "#ebebeb", "#000000", "#f9f9f9", "#7e7e7e4d", "#000000"),
        },
        "bearded-theme-vivid-purple": {
            "style": "Fusion",
            # Bearded Theme Vivid Purple (dark)
            "palette": lambda: manager.create_palette("#171131", "#130e29", "#a699db", "#201844", "#a680ff4d", "#a699db"),
        },
        "bearded-theme-void": {
            "style": "Fusion",
            # Bearded Theme Void (dark)
            "palette": lambda: manager.create_palette("#171322", "#120f1b", "#aa9fc8", "#221c32", "#7a63ed4d", "#aa9fc8"),
        },
        "beatrice-theme": {
            "style": "Fusion",
            # Beatrice Theme (light)
            "palette": lambda: manager.create_palette("#FFE5F1", "#FFE5F1", "#000000", "#FFE0F0", "#fcc9f2aa", "#000000"),
        },
        "bespin-dark": {
            "style": "Fusion",
            # Bespin Dark (dark)
            "palette": lambda: manager.create_palette("#28211c", "#36312e", "#8a8986", "#28211c", "#5e5d5c", "#8a8986"),
        },
        "bespin-light": {
            "style": "Fusion",
            # Bespin Light (light)
            "palette": lambda: manager.create_palette("#baae9e", "#9d9b97", "#5e5d5c", "#baae9e", "#8a8986", "#5e5d5c"),
        },
        "brewer-dark": {
            "style": "Fusion",
            # Brewer Dark (dark)
            "palette": lambda: manager.create_palette("#0c0d0e", "#2e2f30", "#b7b8b9", "#0c0d0e", "#515253", "#b7b8b9"),
        },
        "brewer-light": {
            "style": "Fusion",
            # Brewer Light (light)
            "palette": lambda: manager.create_palette("#fcfdfe", "#dadbdc", "#515253", "#fcfdfe", "#b7b8b9", "#515253"),
        },
        "bright-dark": {
            "style": "Fusion",
            # Bright Dark (dark)
            "palette": lambda: manager.create_palette("#000000", "#303030", "#e0e0e0", "#000000", "#505050", "#e0e0e0"),
        },
        "bright-light": {
            "style": "Fusion",
            # Bright Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#f5f5f5", "#505050", "#ffffff", "#e0e0e0", "#505050"),
        },
        "c-c-theme": {
            "style": "Fusion",
            # C C Theme (light)
            "palette": lambda: manager.create_palette("#C4EA8A", "#C4EA8A", "#101010", "#caec92", "#92d564", "#101010"),
        },
        "catrina-dark-color-light-theme": {
            "style": "Fusion",
            # Catrina Dark Color Light Theme (dark)
            "palette": lambda: manager.create_palette("#150500", "#170505", "#ffe829", "#210e00", "#b07caa40", "#ffe829"),
        },
        "chalk-dark": {
            "style": "Fusion",
            # Chalk Dark (dark)
            "palette": lambda: manager.create_palette("#151515", "#151515", "#d0d0d0", "#151515", "#303030", "#FFFFFF"),
        },
        "chalk-light": {
            "style": "Fusion",
            # Chalk Light (light)
            "palette": lambda: manager.create_palette("#f5f5f5", "#f5f5f5", "#303030", "#f5f5f5", "#e0e0e0", "#FFFFFF"),
        },
        "chocola-theme": {
            "style": "Fusion",
            # Chocola Theme (dark)
            "palette": lambda: manager.create_palette("#2c2729", "#2c2729", "#d3d3d3", "#2c2428", "#6a3849", "#d3d3d3"),
        },
        "christmas-chocola-theme": {
            "style": "Fusion",
            # Christmas Chocola Theme (dark)
            "palette": lambda: manager.create_palette("#3a141d", "#37131b", "#d3d3d3", "#37131b", "#1f422d", "#d3d3d3"),
        },
        "cinnamon-theme": {
            "style": "Fusion",
            # Cinnamon Theme (dark)
            "palette": lambda: manager.create_palette("#343277", "#343277", "#f3edff", "#37357f", "#3a6c75", "#f3edff"),
        },
        "coconut-theme": {
            "style": "Fusion",
            # Coconut Theme (dark)
            "palette": lambda: manager.create_palette("#312b3a", "#312b3a", "#d3d3d3", "#312c3a", "#255b82", "#d3d3d3"),
        },
        "code-blue-theme": {
            "style": "Fusion",
            # Code Blue Theme (dark)
            "palette": lambda: manager.create_palette("#2a324b", "#242b40", "#e2e6e9", "#303956", "#5b6ca299", "#FFFFFF"),
        },
        "codeschool-dark": {
            "style": "Fusion",
            # Codeschool Dark (dark)
            "palette": lambda: manager.create_palette("#232c31", "#1c3657", "#9ea7a6", "#232c31", "#2a343a", "#9ea7a6"),
        },
        "codeschool-light": {
            "style": "Fusion",
            # Codeschool Light (light)
            "palette": lambda: manager.create_palette("#b5d8f6", "#a7cfa3", "#2a343a", "#b5d8f6", "#9ea7a6", "#2a343a"),
        },
        "codestackr-theme-muted": {
            "style": "Fusion",
            # Codestackr Theme Muted (dark)
            "palette": lambda: manager.create_palette("#09131b", "#0a1620", "#FFFFFF", "#0a1620", "#ffb59a80", "#FFFFFF"),
        },
        "codestackr-theme": {
            "style": "Fusion",
            # Codestackr Theme (dark)
            "palette": lambda: manager.create_palette("#09131b", "#0a1620", "#FFFFFF", "#0a1620", "#FF652F80", "#FFFFFF"),
        },
        "colors-dark": {
            "style": "Fusion",
            # Colors Dark (dark)
            "palette": lambda: manager.create_palette("#111111", "#111111", "#bbbbbb", "#111111", "#555555", "#FFFFFF"),
        },
        "colors-light": {
            "style": "Fusion",
            # Colors Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#ffffff", "#555555", "#ffffff", "#dddddd", "#FFFFFF"),
        },
        "cpptools_light_vs": {
            "style": "Fusion",
            # Cpptools Light Vs (dark)
            "palette": lambda: manager.create_palette("#FFFFFF", "#FFFFFF", "#000000", "#FFFFFF", "#0078D4", "#FFFFFF"),
        },
        "custom-dark-theme-color-theme": {
            "style": "Fusion",
            # Custom Dark Theme Color Theme (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#ffffff", "#000000", "#264f78", "#ffffff"),
        },
        "cyberpink-theme": {
            "style": "Fusion",
            # Cyberpink Theme (dark)
            "palette": lambda: manager.create_palette("#07001a", "#07001a", "#ff007b", "#0c002d", "#7e0eff40", "#ff007b"),
        },
        "cyberpunk-umbra-color-theme": {
            "style": "Fusion",
            # Cyberpunk Umbra Color Theme (dark)
            "palette": lambda: manager.create_palette("#100d23", "#1e1d45", "#ffffff", "#002212ec", "#311b92", "#ffffff"),
        },
        "darcula": {
            "style": "Fusion",
            # Darcula (dark)
            "palette": lambda: manager.create_palette("#242424", "#242424", "#cccccc", "#242424", "#204182cc", "#FFFFFF"),
        },
        "darcula_20200805110628": {
            "style": "Fusion",
            # Darcula 20200805110628 (dark)
            "palette": lambda: manager.create_palette("#242424", "#242424", "#A9B7C6", "#242424", "#204182cc", "#FFFFFF"),
        },
        "dark-colorblind": {
            "style": "Fusion",
            # Dark Colorblind (dark)
            "palette": lambda: manager.create_palette("#0d1117", "#010409", "#c9d1d9", "#161b22", "#6e768166", "#c9d1d9"),
        },
        "dark-default": {
            "style": "Fusion",
            # Dark Default (dark)
            "palette": lambda: manager.create_palette("#0d1117", "#010409", "#e6edf3", "#161b22", "#6e768166", "#e6edf3"),
        },
        "dark-dimmed": {
            "style": "Fusion",
            # Dark Dimmed (dark)
            "palette": lambda: manager.create_palette("#22272e", "#1c2128", "#adbac7", "#2d333b", "#636e7b66", "#adbac7"),
        },
        "dark-high-contrast": {
            "style": "Fusion",
            # Dark High Contrast (dark)
            "palette": lambda: manager.create_palette("#0a0c10", "#010409", "#f0f3f6", "#272b33", "#ffffff", "#f0f3f6"),
        },
        "dark": {
            "style": "Fusion",
            # Dark (dark)
            "palette": lambda: manager.create_palette("#24292e", "#1f2428", "#d1d5da", "#1f2428", "#3392FF44", "#d1d5da"),
        },
        "dark_spinel": {
            "style": "Fusion",
            # Dark Spinel (dark)
            "palette": lambda: manager.create_palette("#2f2f2f", "#282828", "#d1ccf1", "#282828", "#4b4b4b", "#FFFFFF"),
        },
        "dark_vs": {
            "style": "Fusion",
            # Dark Vs (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#D4D4D4", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "darkanian-black-lite": {
            "style": "Fusion",
            # Darkanian Black Lite (dark)
            "palette": lambda: manager.create_palette("#000", "#000", "#ffffffbb", "#151718", "#00e67640", "#ffffffbb"),
        },
        "darkanian-black": {
            "style": "Fusion",
            # Darkanian Black (dark)
            "palette": lambda: manager.create_palette("#000", "#000", "#ffffffbb", "#151718", "#00e67640", "#ffffffbb"),
        },
        "darkanian-darcula-new": {
            "style": "Fusion",
            # Darkanian Darcula New (dark)
            "palette": lambda: manager.create_palette("#242424", "#242424", "#cccccc", "#242424", "#204182cc", "#FFFFFF"),
        },
        "darkanian-darcula": {
            "style": "Fusion",
            # Darkanian Darcula (dark)
            "palette": lambda: manager.create_palette("#242424", "#242424", "#cccccc", "#242424", "#204182cc", "#FFFFFF"),
        },
        "darkanian-dimmed-lite": {
            "style": "Fusion",
            # Darkanian Dimmed Lite (dark)
            "palette": lambda: manager.create_palette("#1d2021", "#1d2021", "#ffffffbb", "#151718", "#00e67640", "#ffffffbb"),
        },
        "darkanian-dimmed": {
            "style": "Fusion",
            # Darkanian Dimmed (dark)
            "palette": lambda: manager.create_palette("#1d2021", "#1d2021", "#ffffffbb", "#151718", "#00e67640", "#ffffffbb"),
        },
        "darkanian-github-dark": {
            "style": "Fusion",
            # Darkanian Github Dark (dark)
            "palette": lambda: manager.create_palette("#0d1117", "#010409", "#c9d1d9", "#161b22", "#58a6ff33", "#c9d1d9"),
        },
        "darkanian-github-dimmed": {
            "style": "Fusion",
            # Darkanian Github Dimmed (dark)
            "palette": lambda: manager.create_palette("#22272e", "#1c2128", "#adbac7", "#2d333b", "#539bf533", "#adbac7"),
        },
        "darkanian-github-soft": {
            "style": "Fusion",
            # Darkanian Github Soft (dark)
            "palette": lambda: manager.create_palette("#24292e", "#1f2428", "#d1d5da", "#1f2428", "#3392FF44", "#d1d5da"),
        },
        "darkanian-gruvbox-hard": {
            "style": "Fusion",
            # Darkanian Gruvbox Hard (dark)
            "palette": lambda: manager.create_palette("#1d2021", "#1d2021", "#ebdbb2", "#1d2021", "#689d6a40", "#ebdbb2"),
        },
        "darkanian-gruvbox-medium": {
            "style": "Fusion",
            # Darkanian Gruvbox Medium (dark)
            "palette": lambda: manager.create_palette("#282828", "#282828", "#ebdbb2", "#282828", "#689d6a40", "#ebdbb2"),
        },
        "darkanian-gruvbox-soft": {
            "style": "Fusion",
            # Darkanian Gruvbox Soft (dark)
            "palette": lambda: manager.create_palette("#32302f", "#32302f", "#ebdbb2", "#32302f", "#689d6a40", "#ebdbb2"),
        },
        "darkanian-mt-darker-hc": {
            "style": "Fusion",
            # Darkanian Mt Darker Hc (dark)
            "palette": lambda: manager.create_palette("#212121", "#1a1a1a", "#EEFFFF", "#212121", "#61616150", "#FFFFFF"),
        },
        "darkanian-mt-default-hc": {
            "style": "Fusion",
            # Darkanian Mt Default Hc (dark)
            "palette": lambda: manager.create_palette("#263238", "#192227", "#EEFFFF", "#263238", "#80CBC420", "#FFFFFF"),
        },
        "darkanian-mt-ocean-hc": {
            "style": "Fusion",
            # Darkanian Mt Ocean Hc (dark)
            "palette": lambda: manager.create_palette("#0F111A", "#090B10", "#8F93A2", "#0F111A", "#717CB450", "#FFFFFF"),
        },
        "darkanian-mt-palenight-hc": {
            "style": "Fusion",
            # Darkanian Mt Palenight Hc (dark)
            "palette": lambda: manager.create_palette("#292D3E", "#1B1E2B", "#A6ACCD", "#292D3E", "#717CB450", "#FFFFFF"),
        },
        "darkanian-one-monokai": {
            "style": "Fusion",
            # Darkanian One Monokai (dark)
            "palette": lambda: manager.create_palette("#282c34", "#21252b", "#FFFFFF", "#21252B", "#3E4451", "#FFFFFF"),
        },
        "darkanian-softdark-lite": {
            "style": "Fusion",
            # Darkanian Softdark Lite (dark)
            "palette": lambda: manager.create_palette("#1a1e20", "#161a1b", "#838c91", "#23292c", "#293035", "#838c91"),
        },
        "darkanian-softdark": {
            "style": "Fusion",
            # Darkanian Softdark (dark)
            "palette": lambda: manager.create_palette("#1a1e20", "#161a1b", "#838c91", "#23292c", "#293035", "#838c91"),
        },
        "darkanian-default": {
            "style": "Fusion",
            # Darkanian Default (dark)
            "palette": lambda: manager.create_palette("#1d2021", "#1d2021", "#ffffffbb", "#151718", "#00e67640", "#ffffffbb"),
        },
        "darkness-dark-theme": {
            "style": "Fusion",
            # Darkness Dark Theme (dark)
            "palette": lambda: manager.create_palette("#0a0904", "#0a0904", "#c3c3c3", "#090802", "#55391988", "#c3c3c3"),
        },
        "darkness-light-theme": {
            "style": "Fusion",
            # Darkness Light Theme (light)
            "palette": lambda: manager.create_palette("#FFFEF9", "#FFFEF9", "#000000", "#FFFEF9", "#fff3b4", "#000000"),
        },
        "default-dark": {
            "style": "Fusion",
            # Default Dark (dark)
            "palette": lambda: manager.create_palette("#181818", "#282828", "#d8d8d8", "#181818", "#383838", "#d8d8d8"),
        },
        "default-light": {
            "style": "Fusion",
            # Default Light (light)
            "palette": lambda: manager.create_palette("#f8f8f8", "#e8e8e8", "#383838", "#f8f8f8", "#d8d8d8", "#383838"),
        },
        "dracula-soft": {
            "style": "Fusion",
            # Dracula Soft (dark)
            "palette": lambda: manager.create_palette("#282A36", "#262626", "#f6f6f4", "#282A36", "#44475A", "#f6f6f4"),
        },
        "dracula2": {
            "style": "Fusion",
            # Dracula (dark)
            "palette": lambda: manager.create_palette("#282A36", "#21222C", "#F8F8F2", "#282A36", "#44475A", "#F8F8F2"),
        },
        "echidna-theme": {
            "style": "Fusion",
            # Echidna Theme (dark)
            "palette": lambda: manager.create_palette("#121014", "#121014", "#a8a8a8", "#171519", "#274540", "#a8a8a8"),
        },
        "eighties-dark": {
            "style": "Fusion",
            # Eighties Dark (dark)
            "palette": lambda: manager.create_palette("#2d2d2d", "#393939", "#d3d0c8", "#2d2d2d", "#515151", "#d3d0c8"),
        },
        "eighties-light": {
            "style": "Fusion",
            # Eighties Light (light)
            "palette": lambda: manager.create_palette("#f2f0ec", "#e8e6df", "#515151", "#f2f0ec", "#d3d0c8", "#515151"),
        },
        "embers-dark": {
            "style": "Fusion",
            # Embers Dark (dark)
            "palette": lambda: manager.create_palette("#16130F", "#2C2620", "#A39A90", "#16130F", "#433B32", "#A39A90"),
        },
        "embers-light": {
            "style": "Fusion",
            # Embers Light (light)
            "palette": lambda: manager.create_palette("#DBD6D1", "#BEB6AE", "#433B32", "#DBD6D1", "#A39A90", "#433B32"),
        },
        "emilia-dark-theme": {
            "style": "Fusion",
            # Emilia Dark Theme (dark)
            "palette": lambda: manager.create_palette("#492d5a", "#492d5a", "#DADADA", "#4c2e5c", "#5C3378", "#DADADA"),
        },
        "emilia-light-theme": {
            "style": "Fusion",
            # Emilia Light Theme (light)
            "palette": lambda: manager.create_palette("#fbf0ff", "#fbf0ff", "#252427", "#fbf0ff", "#c7a0d233", "#252427"),
        },
        "essex-theme": {
            "style": "Fusion",
            # Essex Theme (dark)
            "palette": lambda: manager.create_palette("#001d39", "#001d39", "#d7d7d7", "#00203e", "#480F0F", "#d7d7d7"),
        },
        "flat-dark": {
            "style": "Fusion",
            # Flat Dark (dark)
            "palette": lambda: manager.create_palette("#2C3E50", "#34495E", "#e0e0e0", "#2C3E50", "#7F8C8D", "#e0e0e0"),
        },
        "flat-light": {
            "style": "Fusion",
            # Flat Light (light)
            "palette": lambda: manager.create_palette("#ECF0F1", "#f5f5f5", "#7F8C8D", "#ECF0F1", "#e0e0e0", "#7F8C8D"),
        },
        "flat-plat": {
            "style": "Fusion",
            # Flat Plat (dark)
            "palette": lambda: manager.create_palette("#2c393f", "#2c393f", "#d4d4d4", "#2c393f", "#0078D4", "#FFFFFF"),
        },
        "frappe": {
            "style": "Fusion",
            # Frappe (dark)
            "palette": lambda: manager.create_palette("#303446", "#292c3c", "#c6d0f5", "#292c3c", "#949cbb40", "#c6d0f5"),
        },
        "gasai-yuno-theme": {
            "style": "Fusion",
            # Gasai Yuno Theme (dark)
            "palette": lambda: manager.create_palette("#150713", "#150713", "#c8c8c8", "#1a0717", "#602b5088", "#c8c8c8"),
        },
        "genos-theme": {
            "style": "Fusion",
            # Genos Theme (dark)
            "palette": lambda: manager.create_palette("#313234", "#313234", "#dbdbdb", "#252627", "#605d51", "#dbdbdb"),
        },
        "google-dark": {
            "style": "Fusion",
            # Google Dark (dark)
            "palette": lambda: manager.create_palette("#1d1f21", "#282a2e", "#c5c8c6", "#1d1f21", "#373b41", "#c5c8c6"),
        },
        "google-light": {
            "style": "Fusion",
            # Google Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#e0e0e0", "#373b41", "#ffffff", "#c5c8c6", "#373b41"),
        },
        "graveyard-color-theme": {
            "style": "Fusion",
            # Graveyard Color Theme (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#cccccc", "#111111", "#263a7862", "#cccccc"),
        },
        "gray-theme": {
            "style": "Fusion",
            # Gray Theme (dark)
            "palette": lambda: manager.create_palette("#35393b", "#35393b", "#b0b0b0", "#363b3d", "#295043", "#b0b0b0"),
        },
        "grayscale-dark": {
            "style": "Fusion",
            # Grayscale Dark (dark)
            "palette": lambda: manager.create_palette("#101010", "#252525", "#b9b9b9", "#101010", "#464646", "#b9b9b9"),
        },
        "grayscale-light": {
            "style": "Fusion",
            # Grayscale Light (light)
            "palette": lambda: manager.create_palette("#f7f7f7", "#e3e3e3", "#464646", "#f7f7f7", "#b9b9b9", "#464646"),
        },
        "greenscreen-dark": {
            "style": "Fusion",
            # Greenscreen Dark (dark)
            "palette": lambda: manager.create_palette("#001100", "#003300", "#00bb00", "#001100", "#005500", "#00bb00"),
        },
        "greenscreen-light": {
            "style": "Fusion",
            # Greenscreen Light (light)
            "palette": lambda: manager.create_palette("#00ff00", "#00dd00", "#005500", "#00ff00", "#00bb00", "#005500"),
        },
        "hanekawa-tsubasa-theme": {
            "style": "Fusion",
            # Hanekawa Tsubasa Theme (dark)
            "palette": lambda: manager.create_palette("#100d11", "#100d11", "#c3c3c3", "#0f0d10", "#5a3b5dAA", "#c3c3c3"),
        },
        "harmonic-dark": {
            "style": "Fusion",
            # Harmonic Dark (dark)
            "palette": lambda: manager.create_palette("#0b1c2c", "#223b54", "#cbd6e2", "#0b1c2c", "#405c79", "#cbd6e2"),
        },
        "harmonic-light": {
            "style": "Fusion",
            # Harmonic Light (light)
            "palette": lambda: manager.create_palette("#f7f9fb", "#e5ebf1", "#405c79", "#f7f9fb", "#cbd6e2", "#405c79"),
        },
        "hatsune-miku-theme": {
            "style": "Fusion",
            # Hatsune Miku Theme (dark)
            "palette": lambda: manager.create_palette("#2f3635", "#2f3635", "#bbbbbb", "#2c3333", "#4c7a7666", "#bbbbbb"),
        },
        "hayase-nagatoro-theme": {
            "style": "Fusion",
            # Hayase Nagatoro Theme (dark)
            "palette": lambda: manager.create_palette("#151515", "#151515", "#bbbbbb", "#1a1a1a", "#5d3e2f88", "#bbbbbb"),
        },
        "hc_black": {
            "style": "Fusion",
            # Hc Black (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#FFFFFF", "#000000", "#FFFFFF", "#FFFFFF"),
        },
        "hc_light": {
            "style": "Fusion",
            # Hc Light (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "hinata-shoyo-theme": {
            "style": "Fusion",
            # Hinata Shoyo Theme (dark)
            "palette": lambda: manager.create_palette("#201c37", "#201c37", "#b0b0b0", "#24203c", "#6a473d", "#b0b0b0"),
        },
        "hiro-x-zero-two-theme": {
            "style": "Fusion",
            # Hiro X Zero Two Theme (dark)
            "palette": lambda: manager.create_palette("#150b24", "#150b24", "#b8b8b8", "#0f071a", "#29466c", "#b8b8b8"),
        },
        "hiro-theme": {
            "style": "Fusion",
            # Hiro Theme (dark)
            "palette": lambda: manager.create_palette("#16171A", "#16171A", "#b0b0b0", "#16171a", "#1d4a88", "#b0b0b0"),
        },
        "ishtar-dark-theme": {
            "style": "Fusion",
            # Ishtar Dark Theme (dark)
            "palette": lambda: manager.create_palette("#110F10", "#110F10", "#c2c2c2", "#0d0b0c", "#55391988", "#c2c2c2"),
        },
        "ishtar-light-theme": {
            "style": "Fusion",
            # Ishtar Light Theme (light)
            "palette": lambda: manager.create_palette("#fffefb", "#fffefb", "#252427", "#fffefb", "#fff5c7", "#252427"),
        },
        "isotope-dark": {
            "style": "Fusion",
            # Isotope Dark (dark)
            "palette": lambda: manager.create_palette("#000000", "#404040", "#d0d0d0", "#000000", "#606060", "#d0d0d0"),
        },
        "isotope-light": {
            "style": "Fusion",
            # Isotope Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#e0e0e0", "#606060", "#ffffff", "#d0d0d0", "#606060"),
        },
        "jabami-yumeko-theme": {
            "style": "Fusion",
            # Jabami Yumeko Theme (dark)
            "palette": lambda: manager.create_palette("#050000", "#050000", "#dbdbdb", "#0b0000", "#390c10", "#dbdbdb"),
        },
        "jahy-theme": {
            "style": "Fusion",
            # Jahy Theme (dark)
            "palette": lambda: manager.create_palette("#1b102e", "#1b102e", "#cbcbcb", "#1e1430", "#452346", "#cbcbcb"),
        },
        "kai-standard": {
            "style": "Fusion",
            # Kai Standard (dark)
            "palette": lambda: manager.create_palette("#0c0c15", "#11111f", "#d3d4d7", "#0e0e21", "#0099ff44", "#d3d4d7"),
        },
        "kanna-theme": {
            "style": "Fusion",
            # Kanna Theme (dark)
            "palette": lambda: manager.create_palette("#1a1426", "#1a1426", "#d0d0d0", "#1a1526", "#492744", "#d0d0d0"),
        },
        "kary-dark": {
            "style": "Fusion",
            # Kary Dark (dark)
            "palette": lambda: manager.create_palette("#1A1A1A", "#171717", "#FFFFFF", "#392620", "#0091FF40", "#FFFFFF"),
        },
        "kary-light": {
            "style": "Fusion",
            # Kary Light (dark)
            "palette": lambda: manager.create_palette("#F0F6FB", "#F1F1F1", "#3778B7", "#FFF5D6", "#E2EEFA", "#FFFFFF"),
        },
        "katsuragi-misato-theme": {
            "style": "Fusion",
            # Katsuragi Misato Theme (dark)
            "palette": lambda: manager.create_palette("#382536", "#382536", "#b5a3b0", "#3d2536", "#5a293f88", "#b5a3b0"),
        },
        "kirino-theme": {
            "style": "Fusion",
            # Kirino Theme (dark)
            "palette": lambda: manager.create_palette("#121e1c", "#121e1c", "#cbcbcb", "#121e1c", "#3d213e", "#cbcbcb"),
        },
        "konata-theme": {
            "style": "Fusion",
            # Konata Theme (dark)
            "palette": lambda: manager.create_palette("#355082", "#355082", "#f3edff", "#314978", "#3a6c75", "#f3edff"),
        },
        "legacy-solarized-dark-color-theme": {
            "style": "Fusion",
            # Legacy Solarized Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#002b36", "#00212b", "#93a1a1", "#004052", "#073642", "#FFFFFF"),
        },
        "legacy-solarized-light-color-theme": {
            "style": "Fusion",
            # Legacy Solarized Light Color Theme (light)
            "palette": lambda: manager.create_palette("#fdf6e3", "#eee8d5", "#586e75", "#ccc4b0", "#eee8d5", "#FFFFFF"),
        },
        "light-colorblind": {
            "style": "Fusion",
            # Light Colorblind (dark)
            "palette": lambda: manager.create_palette("#ffffff", "#f6f8fa", "#24292f", "#ffffff", "#afb8c133", "#24292f"),
        },
        "light-default": {
            "style": "Fusion",
            # Light Default (dark)
            "palette": lambda: manager.create_palette("#ffffff", "#f6f8fa", "#1f2328", "#ffffff", "#afb8c133", "#1f2328"),
        },
        "light-high-contrast": {
            "style": "Fusion",
            # Light High Contrast (dark)
            "palette": lambda: manager.create_palette("#ffffff", "#ffffff", "#0e1116", "#ffffff", "#0e1116", "#0e1116"),
        },
        "light_modern": {
            "style": "Fusion",
            # Light Modern (dark)
            "palette": lambda: manager.create_palette("#FFFFFF", "#F8F8F8", "#3B3B3B", "#F8F8F8", "#E8E8E8", "#3B3B3B"),
        },
        "light_spinel": {
            "style": "Fusion",
            # Light Spinel (light)
            "palette": lambda: manager.create_palette("#e3e2ec", "#e6e5ee", "#595959", "#e6e6ec", "#d8d8db", "#FFFFFF"),
        },
        "light_vs": {
            "style": "Fusion",
            # Light Vs (dark)
            "palette": lambda: manager.create_palette("#FFFFFF", "#FFFFFF", "#000000", "#FFFFFF", "#0078D4", "#FFFFFF"),
        },
        "londontube-dark": {
            "style": "Fusion",
            # Londontube Dark (dark)
            "palette": lambda: manager.create_palette("#231f20", "#231f20", "#d9d8d8", "#231f20", "#5a5758", "#FFFFFF"),
        },
        "londontube-light": {
            "style": "Fusion",
            # Londontube Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#ffffff", "#5a5758", "#ffffff", "#e7e7e8", "#FFFFFF"),
        },
        "macchiato": {
            "style": "Fusion",
            # Macchiato (dark)
            "palette": lambda: manager.create_palette("#24273a", "#1e2030", "#cad3f5", "#1e2030", "#939ab740", "#cad3f5"),
        },
        "mai-dark-theme": {
            "style": "Fusion",
            # Mai Dark Theme (dark)
            "palette": lambda: manager.create_palette("#242448", "#242448", "#bbbbbb", "#25254e", "#23516199", "#bbbbbb"),
        },
        "mai-light-theme": {
            "style": "Fusion",
            # Mai Light Theme (light)
            "palette": lambda: manager.create_palette("#FAF2F1", "#FAF2F1", "#252427", "#fff7f6", "#d3d5f1", "#252427"),
        },
        "maika-theme": {
            "style": "Fusion",
            # Maika Theme (dark)
            "palette": lambda: manager.create_palette("#24062f", "#24062f", "#c9c9c9", "#20052a", "#3d1535", "#c9c9c9"),
        },
        "makise-kurisu-theme": {
            "style": "Fusion",
            # Makise Kurisu Theme (dark)
            "palette": lambda: manager.create_palette("#170a0b", "#170a0b", "#c3c3c3", "#1a0e0e", "#391717", "#c3c3c3"),
        },
        "maple-dark-theme": {
            "style": "Fusion",
            # Maple Dark Theme (dark)
            "palette": lambda: manager.create_palette("#2d1d1d", "#2d1d1d", "#cccccc", "#2f1b1b", "#295043", "#cccccc"),
        },
        "maple-light-theme": {
            "style": "Fusion",
            # Maple Light Theme (light)
            "palette": lambda: manager.create_palette("#ffd091", "#ffd091", "#101010", "#fdcd8f", "#ec9e74", "#101010"),
        },
        "marrakesh-dark": {
            "style": "Fusion",
            # Marrakesh Dark (dark)
            "palette": lambda: manager.create_palette("#201602", "#302e00", "#948e48", "#201602", "#5f5b17", "#948e48"),
        },
        "marrakesh-light": {
            "style": "Fusion",
            # Marrakesh Light (light)
            "palette": lambda: manager.create_palette("#faf0a5", "#ccc37a", "#5f5b17", "#faf0a5", "#948e48", "#5f5b17"),
        },
        "material-theme-darker-high-contrast": {
            "style": "Fusion",
            # Material Theme Darker High Contrast (dark)
            "palette": lambda: manager.create_palette("#212121", "#1a1a1a", "#EEFFFF", "#212121", "#61616150", "#EEFFFF"),
        },
        "material-theme-darker2": {
            "style": "Fusion",
            # Material Theme Darker (dark)
            "palette": lambda: manager.create_palette("#212121", "#212121", "#EEFFFF", "#212121", "#61616150", "#EEFFFF"),
        },
        "material-theme-deepforest-high-contrast": {
            "style": "Fusion",
            # Material Theme Deepforest High Contrast (dark)
            "palette": lambda: manager.create_palette("#141F1D", "#101917", "#C2EDD3", "#141F1D", "#71B48050", "#C2EDD3"),
        },
        "material-theme-deepforest": {
            "style": "Fusion",
            # Material Theme Deepforest (dark)
            "palette": lambda: manager.create_palette("#141F1D", "#141F1D", "#C2EDD3", "#141F1D", "#71B48050", "#C2EDD3"),
        },
        "material-theme-default-high-contrast": {
            "style": "Fusion",
            # Material Theme Default High Contrast (dark)
            "palette": lambda: manager.create_palette("#263238", "#192227", "#EEFFFF", "#263238", "#80CBC420", "#EEFFFF"),
        },
        "material-theme-default2": {
            "style": "Fusion",
            # Material Theme Default (dark)
            "palette": lambda: manager.create_palette("#263238", "#263238", "#EEFFFF", "#263238", "#80CBC420", "#EEFFFF"),
        },
        "material-theme-lighter-high-contrast": {
            "style": "Fusion",
            # Material Theme Lighter High Contrast (dark)
            "palette": lambda: manager.create_palette("#FFFFFF", "#FAFAFA", "#90A4AE", "#FFFFFF", "#80CBC440", "#90A4AE"),
        },
        "material-theme-lighter": {
            "style": "Fusion",
            # Material Theme Lighter (dark)
            "palette": lambda: manager.create_palette("#FAFAFA", "#FAFAFA", "#90A4AE", "#FAFAFA", "#80CBC440", "#90A4AE"),
        },
        "material-theme-ocean-high-contrast": {
            "style": "Fusion",
            # Material Theme Ocean High Contrast (dark)
            "palette": lambda: manager.create_palette("#0F111A", "#090B10", "#babed8", "#0F111A", "#717CB450", "#babed8"),
        },
        "material-theme-palenight-high-contrast": {
            "style": "Fusion",
            # Material Theme Palenight High Contrast (dark)
            "palette": lambda: manager.create_palette("#292D3E", "#1B1E2B", "#babed8", "#292D3E", "#717CB450", "#babed8"),
        },
        "material-theme-palenight2": {
            "style": "Fusion",
            # Material Theme Palenight (dark)
            "palette": lambda: manager.create_palette("#292D3E", "#292D3E", "#babed8", "#292D3E", "#717CB450", "#babed8"),
        },
        "megumin-theme": {
            "style": "Fusion",
            # Megumin Theme (dark)
            "palette": lambda: manager.create_palette("#2c2126", "#2c2126", "#bbbbbb", "#2a1f24", "#56303688", "#bbbbbb"),
        },
        "miia-theme": {
            "style": "Fusion",
            # Miia Theme (dark)
            "palette": lambda: manager.create_palette("#310e19", "#310e19", "#efefef", "#3a1020", "#5b322588", "#efefef"),
        },
        "mioda-ibuki-dark-theme": {
            "style": "Fusion",
            # Mioda Ibuki Dark Theme (dark)
            "palette": lambda: manager.create_palette("#191b1d", "#191b1d", "#bbbbbb", "#17191b", "#452735", "#bbbbbb"),
        },
        "mioda-ibuki-light-theme": {
            "style": "Fusion",
            # Mioda Ibuki Light Theme (light)
            "palette": lambda: manager.create_palette("#ffeefd", "#ffeefd", "#272426", "#ffeefd", "#8EDBFF55", "#272426"),
        },
        "misaka-mikoto-theme": {
            "style": "Fusion",
            # Misaka Mikoto Theme (dark)
            "palette": lambda: manager.create_palette("#0b173a", "#0b173a", "#dbdbdb", "#0b1633", "#05649c", "#dbdbdb"),
        },
        "mocha-dark": {
            "style": "Fusion",
            # Mocha Dark (dark)
            "palette": lambda: manager.create_palette("#3B3228", "#534636", "#d0c8c6", "#3B3228", "#645240", "#d0c8c6"),
        },
        "mocha-light": {
            "style": "Fusion",
            # Mocha Light (light)
            "palette": lambda: manager.create_palette("#f5eeeb", "#e9e1dd", "#645240", "#f5eeeb", "#d0c8c6", "#645240"),
        },
        "mocha": {
            "style": "Fusion",
            # Mocha (dark)
            "palette": lambda: manager.create_palette("#1e1e2e", "#181825", "#cdd6f4", "#181825", "#9399b240", "#cdd6f4"),
        },
        "monika-dark-theme": {
            "style": "Fusion",
            # Monika Dark Theme (dark)
            "palette": lambda: manager.create_palette("#1d2115", "#1d2115", "#bbbbbb", "#1D2115", "#30432B88", "#bbbbbb"),
        },
        "monika-light-theme": {
            "style": "Fusion",
            # Monika Light Theme (light)
            "palette": lambda: manager.create_palette("#f2fff0", "#f2fff0", "#252427", "#f2fff0", "#a9ecac66", "#252427"),
        },
        "monokai-classic": {
            "style": "Fusion",
            # Monokai Classic (dark)
            "palette": lambda: manager.create_palette("#272822", "#1d1e19", "#fdfff1", "#3b3c35", "#c0c1b526", "#fdfff1"),
        },
        "monokai-pro-filter-machine": {
            "style": "Fusion",
            # Monokai Pro Filter Machine (dark)
            "palette": lambda: manager.create_palette("#273136", "#1d2528", "#f2fffc", "#3a4449", "#b8c4c326", "#f2fffc"),
        },
        "monokai-pro-filter-octagon": {
            "style": "Fusion",
            # Monokai Pro Filter Octagon (dark)
            "palette": lambda: manager.create_palette("#282a3a", "#1e1f2b", "#eaf2f1", "#3a3d4b", "#b2b9bd26", "#eaf2f1"),
        },
        "monokai-pro-filter-ristretto": {
            "style": "Fusion",
            # Monokai Pro Filter Ristretto (dark)
            "palette": lambda: manager.create_palette("#2c2525", "#211c1c", "#fff1f3", "#403838", "#c3b7b826", "#fff1f3"),
        },
        "monokai-pro-filter-spectrum": {
            "style": "Fusion",
            # Monokai Pro Filter Spectrum (dark)
            "palette": lambda: manager.create_palette("#222222", "#191919", "#f7f1ff", "#363537", "#bab6c026", "#f7f1ff"),
        },
        "monokai-pro2": {
            "style": "Fusion",
            # Monokai Pro (dark)
            "palette": lambda: manager.create_palette("#2d2a2e", "#221f22", "#fcfcfa", "#403e41", "#c1c0c026", "#fcfcfa"),
        },
        "monokai-charcoal-gray": {
            "style": "Fusion",
            # Monokai Charcoal Gray (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal-green": {
            "style": "Fusion",
            # Monokai Charcoal Green (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal-orange": {
            "style": "Fusion",
            # Monokai Charcoal Orange (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal-purple": {
            "style": "Fusion",
            # Monokai Charcoal Purple (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal-red": {
            "style": "Fusion",
            # Monokai Charcoal Red (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal-white": {
            "style": "Fusion",
            # Monokai Charcoal White (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal-yellow": {
            "style": "Fusion",
            # Monokai Charcoal Yellow (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-charcoal": {
            "style": "Fusion",
            # Monokai Charcoal (dark)
            "palette": lambda: manager.create_palette("#000000", "#000", "#FFFFFF", "#000000", "#6688cc", "#FFFFFF"),
        },
        "monokai-dark": {
            "style": "Fusion",
            # Monokai Dark (dark)
            "palette": lambda: manager.create_palette("#272822", "#383830", "#f8f8f2", "#272822", "#49483e", "#f8f8f2"),
        },
        "monokai-light": {
            "style": "Fusion",
            # Monokai Light (light)
            "palette": lambda: manager.create_palette("#f9f8f5", "#f5f4f1", "#49483e", "#f9f8f5", "#f8f8f2", "#49483e"),
        },
        "nadeshiko-theme": {
            "style": "Fusion",
            # Nadeshiko Theme (dark)
            "palette": lambda: manager.create_palette("#2c1f26", "#2c1f26", "#b0b0b0", "#2f2128", "#553854", "#b0b0b0"),
        },
        "nakano-ichika-theme": {
            "style": "Fusion",
            # Nakano Ichika Theme (light)
            "palette": lambda: manager.create_palette("#E3CCFD", "#E3CCFD", "#101010", "#e2c9fa", "#f1b7d6", "#101010"),
        },
        "nakano-itsuki-theme": {
            "style": "Fusion",
            # Nakano Itsuki Theme (light)
            "palette": lambda: manager.create_palette("#FFBEBE", "#FFBEBE", "#101010", "#fcc1c1", "#f4665a", "#101010"),
        },
        "nakano-miku-theme": {
            "style": "Fusion",
            # Nakano Miku Theme (dark)
            "palette": lambda: manager.create_palette("#244158", "#244158", "#f3edff", "#24445b", "#49819266", "#f3edff"),
        },
        "nakano-nino-theme": {
            "style": "Fusion",
            # Nakano Nino Theme (dark)
            "palette": lambda: manager.create_palette("#1c191d", "#1c191d", "#bbbbbb", "#1f1a1f", "#452735", "#bbbbbb"),
        },
        "nakano-yotsuba-theme": {
            "style": "Fusion",
            # Nakano Yotsuba Theme (dark)
            "palette": lambda: manager.create_palette("#200909", "#110c15", "#bbbbbb", "#110c15", "#62231688", "#bbbbbb"),
        },
        "natsuki-dark-theme": {
            "style": "Fusion",
            # Natsuki Dark Theme (dark)
            "palette": lambda: manager.create_palette("#35102c", "#35102c", "#bbbbbb", "#2f0a27", "#602b5066", "#bbbbbb"),
        },
        "natsuki-light-theme": {
            "style": "Fusion",
            # Natsuki Light Theme (light)
            "palette": lambda: manager.create_palette("#FFE5F1", "#FFE5F1", "#000000", "#FFE0F0", "#fcc9f2aa", "#000000"),
        },
        "netbeanslight": {
            "style": "Fusion",
            # Netbeanslight (light)
            "palette": lambda: manager.create_palette("#ffffff", "#ffffff", "#000000", "#ffffff", "#b0c5e3", "#FFFFFF"),
        },
        "night-owl-color-theme-noitalic": {
            "style": "Fusion",
            # Night Owl Color Theme Noitalic (dark)
            "palette": lambda: manager.create_palette("#011627", "#011627", "#d6deeb", "#011627", "#1d3b53", "#d6deeb"),
        },
        "night-owl-color-theme": {
            "style": "Fusion",
            # Night Owl Color Theme (dark)
            "palette": lambda: manager.create_palette("#011627", "#011627", "#d6deeb", "#011627", "#1d3b53", "#d6deeb"),
        },
        "night-owl-light-color-theme-noitalic": {
            "style": "Fusion",
            # Night Owl Light Color Theme Noitalic (light)
            "palette": lambda: manager.create_palette("#FBFBFB", "#F0F0F0", "#403f53", "#F0F0F0", "#E0E0E0", "#403f53"),
        },
        "ocean-dark": {
            "style": "Fusion",
            # Ocean Dark (dark)
            "palette": lambda: manager.create_palette("#2b303b", "#343d46", "#c0c5ce", "#2b303b", "#4f5b66", "#c0c5ce"),
        },
        "ocean-light": {
            "style": "Fusion",
            # Ocean Light (light)
            "palette": lambda: manager.create_palette("#eff1f5", "#dfe1e8", "#4f5b66", "#eff1f5", "#c0c5ce", "#4f5b66"),
        },
        "oceanicnext-dark": {
            "style": "Fusion",
            # Oceanicnext Dark (dark)
            "palette": lambda: manager.create_palette("#1B2B34", "#343D46", "#C0C5CE", "#1B2B34", "#4F5B66", "#C0C5CE"),
        },
        "oceanicnext-light": {
            "style": "Fusion",
            # Oceanicnext Light (light)
            "palette": lambda: manager.create_palette("#D8DEE9", "#CDD3DE", "#4F5B66", "#D8DEE9", "#C0C5CE", "#4F5B66"),
        },
        "onedark2": {
            "style": "Fusion",
            # Onedark (dark)
            "palette": lambda: manager.create_palette("#282C34", "#21252B", "#ABB2BF", "#21252B", "#3E4451", "#FFFFFF"),
        },
        "orange-light-color-theme": {
            "style": "Fusion",
            # Orange Light Color Theme (light)
            "palette": lambda: manager.create_palette("#ffffff", "#f3f3f3", "#616161", "#f3f3f3", "#add6ff", "#616161"),
        },
        "paraiso-dark": {
            "style": "Fusion",
            # Paraiso Dark (dark)
            "palette": lambda: manager.create_palette("#2f1e2e", "#41323f", "#a39e9b", "#2f1e2e", "#4f424c", "#a39e9b"),
        },
        "paraiso-light": {
            "style": "Fusion",
            # Paraiso Light (light)
            "palette": lambda: manager.create_palette("#e7e9db", "#b9b6b0", "#4f424c", "#e7e9db", "#a39e9b", "#4f424c"),
        },
        "pink-cat-boo": {
            "style": "Fusion",
            # Pink Cat Boo (dark)
            "palette": lambda: manager.create_palette("#202330", "#2d2f42", "#FFF0F5", "#2d2f42", "#472541", "#FFFFFF"),
        },
        "pop-dark": {
            "style": "Fusion",
            # Pop Dark (dark)
            "palette": lambda: manager.create_palette("#000000", "#202020", "#d0d0d0", "#000000", "#303030", "#d0d0d0"),
        },
        "pop-light": {
            "style": "Fusion",
            # Pop Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#e0e0e0", "#303030", "#ffffff", "#d0d0d0", "#303030"),
        },
        "radical": {
            "style": "Fusion",
            # Radical (dark)
            "palette": lambda: manager.create_palette("#141322", "#12111f", "#7c9c9e", "#262b4be6", "#874df84d", "#7c9c9e"),
        },
        "railscasts-dark": {
            "style": "Fusion",
            # Railscasts Dark (dark)
            "palette": lambda: manager.create_palette("#2b2b2b", "#272935", "#e6e1dc", "#2b2b2b", "#3a4055", "#e6e1dc"),
        },
        "railscasts-light": {
            "style": "Fusion",
            # Railscasts Light (light)
            "palette": lambda: manager.create_palette("#f9f7f3", "#f4f1ed", "#3a4055", "#f9f7f3", "#e6e1dc", "#3a4055"),
        },
        "ram-theme": {
            "style": "Fusion",
            # Ram Theme (dark)
            "palette": lambda: manager.create_palette("#342c34", "#342c34", "#bbbbbb", "#2b252b", "#7a546f88", "#bbbbbb"),
        },
        "raphtalia-theme": {
            "style": "Fusion",
            # Raphtalia Theme (dark)
            "palette": lambda: manager.create_palette("#1e1710", "#1e1710", "#cccccc", "#1c140f", "#5c3915", "#cccccc"),
        },
        "rei-theme": {
            "style": "Fusion",
            # Rei Theme (dark)
            "palette": lambda: manager.create_palette("#191b1f", "#191b1f", "#d2d2d2", "#131514", "#25435a88", "#d2d2d2"),
        },
        "rem-theme": {
            "style": "Fusion",
            # Rem Theme (dark)
            "palette": lambda: manager.create_palette("#2c2d34", "#2c2d34", "#bbbbbb", "#25262b", "#4C637A88", "#bbbbbb"),
        },
        "rias-crimson-theme": {
            "style": "Fusion",
            # Rias Crimson Theme (dark)
            "palette": lambda: manager.create_palette("#3E1010", "#3E1010", "#fafafa", "#3d1313", "#822e2e45", "#fafafa"),
        },
        "rias-onyx-theme": {
            "style": "Fusion",
            # Rias Onyx Theme (dark)
            "palette": lambda: manager.create_palette("#100000", "#100000", "#d8d8d8", "#100000", "#390c10", "#d8d8d8"),
        },
        "rimiru-tempest-theme": {
            "style": "Fusion",
            # Rimiru Tempest Theme (dark)
            "palette": lambda: manager.create_palette("#1c171d", "#1c171d", "#d3d3d3", "#211c22", "#29466c", "#d3d3d3"),
        },
        "rimuru-tempest-theme": {
            "style": "Fusion",
            # Rimuru Tempest Theme (dark)
            "palette": lambda: manager.create_palette("#1c171d", "#1c171d", "#d3d3d3", "#211c22", "#29466c", "#d3d3d3"),
        },
        "rory-mercury-theme": {
            "style": "Fusion",
            # Rory Mercury Theme (dark)
            "palette": lambda: manager.create_palette("#141417", "#141417", "#c3c3c3", "#18181b", "#502121", "#c3c3c3"),
        },
        "rose-pink-color-theme": {
            "style": "Fusion",
            # Rose Pink Color Theme (dark)
            "palette": lambda: manager.create_palette("#281016", "#49292f", "#c1b492", "#3b1922", "#50283280", "#c1b492"),
        },
        "ryuko-dark-theme": {
            "style": "Fusion",
            # Ryuko Dark Theme (dark)
            "palette": lambda: manager.create_palette("#2b3238", "#2b3238", "#bbbbbb", "#2b3238", "#56303688", "#bbbbbb"),
        },
        "ryuko-light-theme": {
            "style": "Fusion",
            # Ryuko Light Theme (light)
            "palette": lambda: manager.create_palette("#ffffff", "#ffffff", "#101010", "#f5f6f7", "#74adec", "#101010"),
        },
        "sagiri-theme": {
            "style": "Fusion",
            # Sagiri Theme (dark)
            "palette": lambda: manager.create_palette("#0a3b36", "#0a3b36", "#f3edff", "#0a3f39", "#052421", "#f3edff"),
        },
        "satsuki-dark-theme": {
            "style": "Fusion",
            # Satsuki Dark Theme (dark)
            "palette": lambda: manager.create_palette("#242729", "#242729", "#d3d3d3", "#212427", "#5d2626", "#d3d3d3"),
        },
        "satsuki-light-theme": {
            "style": "Fusion",
            # Satsuki Light Theme (light)
            "palette": lambda: manager.create_palette("#ffffff", "#ffffff", "#101010", "#f5f6f7", "#748fecAA", "#101010"),
        },
        "sayori-dark-theme": {
            "style": "Fusion",
            # Sayori Dark Theme (dark)
            "palette": lambda: manager.create_palette("#111b2d", "#111b2d", "#bbbbbb", "#0e1b2f", "#23416488", "#bbbbbb"),
        },
        "sayori-light-theme": {
            "style": "Fusion",
            # Sayori Light Theme (light)
            "palette": lambda: manager.create_palette("#f0faff", "#f0faff", "#252427", "#f0faff", "#a9c8ecaa", "#252427"),
        },
        "senko-theme": {
            "style": "Fusion",
            # Senko Theme (light)
            "palette": lambda: manager.create_palette("#FFE7CD", "#FFE7CD", "#073642", "#fce2c6", "#f4ac96", "#073642"),
        },
        "shapeshifter-dark": {
            "style": "Fusion",
            # Shapeshifter Dark (dark)
            "palette": lambda: manager.create_palette("#000000", "#040404", "#ababab", "#000000", "#102015", "#ababab"),
        },
        "shapeshifter-light": {
            "style": "Fusion",
            # Shapeshifter Light (light)
            "palette": lambda: manager.create_palette("#f9f9f9", "#e0e0e0", "#102015", "#f9f9f9", "#ababab", "#102015"),
        },
        "shigure-theme": {
            "style": "Fusion",
            # Shigure Theme (light)
            "palette": lambda: manager.create_palette("#e9e9ff", "#e9e9ff", "#101010", "#dad9ff", "#5756a288", "#101010"),
        },
        "shima-rin-theme": {
            "style": "Fusion",
            # Shima Rin Theme (dark)
            "palette": lambda: manager.create_palette("#2b303b", "#2b303b", "#b0b0b0", "#2e343e", "#4f3a4eAA", "#b0b0b0"),
        },
        "solarized-dark": {
            "style": "Fusion",
            # Solarized Dark (dark)
            "palette": lambda: manager.create_palette("#002b36", "#073642", "#93a1a1", "#002b36", "#586e75", "#93a1a1"),
        },
        "solarized-light": {
            "style": "Fusion",
            # Solarized Light (light)
            "palette": lambda: manager.create_palette("#fdf6e3", "#eee8d5", "#586e75", "#fdf6e3", "#93a1a1", "#586e75"),
        },
        "sonoda-umi-theme": {
            "style": "Fusion",
            # Sonoda Umi Theme (dark)
            "palette": lambda: manager.create_palette("#15173c", "#15173c", "#d0d0d0", "#191b44", "#272A59", "#d0d0d0"),
        },
        "summerfruit-dark": {
            "style": "Fusion",
            # Summerfruit Dark (dark)
            "palette": lambda: manager.create_palette("#151515", "#202020", "#D0D0D0", "#151515", "#303030", "#D0D0D0"),
        },
        "summerfruit-light": {
            "style": "Fusion",
            # Summerfruit Light (light)
            "palette": lambda: manager.create_palette("#FFFFFF", "#E0E0E0", "#101010", "#FFFFFF", "#D0D0D0", "#101010"),
        },
        "synthwave-x-fluoromachine": {
            "style": "Fusion",
            # Synthwave X Fluoromachine (dark)
            "palette": lambda: manager.create_palette("#262335", "#241b2f", "#ffffff", "#232530", "#46346588", "#ffffff"),
        },
        "takanashi-rikka-theme": {
            "style": "Fusion",
            # Takanashi Rikka Theme (dark)
            "palette": lambda: manager.create_palette("#1e1928", "#1e1928", "#bbbbbb", "#1d1926", "#761d3a88", "#bbbbbb"),
        },
        "theme": {
            "style": "Fusion",
            # Theme (dark)
            "palette": lambda: manager.create_palette("#380e10", "#380e10", "#f78888", "#5a0a0a", "#68551a", "#f78888"),
        },
        "themes-color-theme": {
            "style": "Fusion",
            # Themes Color Theme (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#808080", "#000000", "#399EF480", "#808080"),
        },
        "tohru-theme": {
            "style": "Fusion",
            # Tohru Theme (light)
            "palette": lambda: manager.create_palette("#ffe090", "#ffe090", "#101010", "#f6d988", "#ec9e7455", "#101010"),
        },
        "tohsaka-rin-theme": {
            "style": "Fusion",
            # Tohsaka Rin Theme (dark)
            "palette": lambda: manager.create_palette("#161415", "#161415", "#bbbbbb", "#1b191a", "#501F1F", "#bbbbbb"),
        },
        "tomori-nao-theme": {
            "style": "Fusion",
            # Tomori Nao Theme (light)
            "palette": lambda: manager.create_palette("#efe7de", "#efe7de", "#101010", "#f1e7de", "#b7c6ef", "#101010"),
        },
        "tomorrow-dark": {
            "style": "Fusion",
            # Tomorrow Dark (dark)
            "palette": lambda: manager.create_palette("#1d1f21", "#282a2e", "#d6d6d6", "#1d1f21", "#4d4d4c", "#d6d6d6"),
        },
        "tomorrow-light": {
            "style": "Fusion",
            # Tomorrow Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#e0e0e0", "#4d4d4c", "#ffffff", "#d6d6d6", "#4d4d4c"),
        },
        "twilight-dark": {
            "style": "Fusion",
            # Twilight Dark (dark)
            "palette": lambda: manager.create_palette("#1e1e1e", "#323537", "#a7a7a7", "#1e1e1e", "#464b50", "#a7a7a7"),
        },
        "twilight-light": {
            "style": "Fusion",
            # Twilight Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#c3c3c3", "#464b50", "#ffffff", "#a7a7a7", "#464b50"),
        },
        "underdark-color-theme": {
            "style": "Fusion",
            # Underdark Color Theme (dark)
            "palette": lambda: manager.create_palette("#0a0a0a", "#0a0a0a", "#999999", "#111111", "#333333", "#999999"),
        },
        "underdark-dark-color-theme": {
            "style": "Fusion",
            # Underdark Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#000000", "#000000", "#999999", "#0a0a0a", "#222d5aa1", "#999999"),
        },
        "underdark-jungle-color-theme": {
            "style": "Fusion",
            # Underdark Jungle Color Theme (dark)
            "palette": lambda: manager.create_palette("#000605", "#000605", "#00a58a", "#001d18", "#002e26", "#00a58a"),
        },
        "underdark-paper-color-theme": {
            "style": "Fusion",
            # Underdark Paper Color Theme (dark)
            "palette": lambda: manager.create_palette("#f5f5f5", "#f5f5f5", "#999999", "#ddffd9", "#d1e7ff", "#999999"),
        },
        "unikitty-dark": {
            "style": "Fusion",
            # Unikitty Dark (dark)
            "palette": lambda: manager.create_palette("#2e2a31", "#4a464d", "#bcbabe", "#2e2a31", "#666369", "#bcbabe"),
        },
        "unikitty-light": {
            "style": "Fusion",
            # Unikitty Light (light)
            "palette": lambda: manager.create_palette("#ffffff", "#e1e1e2", "#6c696e", "#ffffff", "#c4c3c5", "#6c696e"),
        },
        "united-gnome": {
            "style": "Fusion",
            # United Gnome (dark)
            "palette": lambda: manager.create_palette("#1e1e1e", "#242424", "#dddddd", "#242424", "#ea542150", "#FFFFFF"),
        },
        "vanilla-theme": {
            "style": "Fusion",
            # Vanilla Theme (dark)
            "palette": lambda: manager.create_palette("#2b2c3d", "#2b2c3d", "#cdcdcd", "#292a3a", "#374872", "#cdcdcd"),
        },
        "winteriscoming-dark-color-no-italics-theme": {
            "style": "Fusion",
            # Winteriscoming Dark Color No Italics Theme (dark)
            "palette": lambda: manager.create_palette("#282822", "#282822", "#d6deeb", "#282822", "#103362", "#d6deeb"),
        },
        "winteriscoming-dark-color-theme": {
            "style": "Fusion",
            # Winteriscoming Dark Color Theme (dark)
            "palette": lambda: manager.create_palette("#282822", "#282822", "#d6deeb", "#282822", "#103362", "#d6deeb"),
        },
        "winteriscoming-light-color-no-italics-theme": {
            "style": "Fusion",
            # Winteriscoming Light Color No Italics Theme (light)
            "palette": lambda: manager.create_palette("#FFFFFF", "#F3F3F3", "#1857a4", "#fff", "#cee1f0", "#1857a4"),
        },
        "winteriscoming-light-color-theme": {
            "style": "Fusion",
            # Winteriscoming Light Color Theme (light)
            "palette": lambda: manager.create_palette("#FFFFFF", "#F3F3F3", "#1857a4", "#fff", "#cee1f0", "#1857a4"),
        },
        "woodland-dark": {
            "style": "Fusion",
            # Woodland Dark (dark)
            "palette": lambda: manager.create_palette("#231e18", "#302b25", "#cabcb1", "#231e18", "#48413a", "#cabcb1"),
        },
        "xcode-civic": {
            "style": "Fusion",
            # Xcode Civic (dark)
            "palette": lambda: manager.create_palette("#232222", "#353333", "#a3a2a2", "#2c2c2b", "#6e6e6e", "#a3a2a2"),
        },
        "yukihira-soma-theme": {
            "style": "Fusion",
            # Yukihira Soma Theme (dark)
            "palette": lambda: manager.create_palette("#09192b", "#09192b", "#dbdbdb", "#0c1c2e", "#4f1d27", "#dbdbdb"),
        },
        "yukinoshita-yukino-theme": {
            "style": "Fusion",
            # Yukinoshita Yukino Theme (dark)
            "palette": lambda: manager.create_palette("#1f2126", "#1f2126", "#bbbbbb", "#282a2f", "#2d3b55AA", "#bbbbbb"),
        },
        "yuri-dark-theme": {
            "style": "Fusion",
            # Yuri Dark Theme (dark)
            "palette": lambda: manager.create_palette("#422D5A", "#422D5A", "#DADADA", "#442e5c", "#663995", "#DADADA"),
        },
        "yuri-light-theme": {
            "style": "Fusion",
            # Yuri Light Theme (light)
            "palette": lambda: manager.create_palette("#f3f0ff", "#f3f0ff", "#252427", "#f5f0ff", "#ada0d233", "#252427"),
        },
        "yuzuriha-inori-theme": {
            "style": "Fusion",
            # Yuzuriha Inori Theme (light)
            "palette": lambda: manager.create_palette("#FFA772", "#FFA772", "#101010", "#f8a56e", "#EC7F54", "#101010"),
        },
        "zeonica-midnight": {
            "style": "Fusion",
            # Zeonica Midnight (dark)
            "palette": lambda: manager.create_palette("#000000", "#060530", "#f5f5ff", "#01001f", "#1c1b75", "#f5f5ff"),
        },
        "zeonica": {
            "style": "Fusion",
            # Zeonica (dark)
            "palette": lambda: manager.create_palette("#01001f", "#060530", "#f5f5ff", "#01001f", "#1c1b75", "#f5f5ff"),
        },
        "zero-two-dark-obsidian-theme": {
            "style": "Fusion",
            # Zero Two Dark Obsidian Theme (dark)
            "palette": lambda: manager.create_palette("#17070e", "#17070e", "#bbbbbb", "#150a0e", "#174a2e", "#bbbbbb"),
        },
        "zero-two-dark-rose-theme": {
            "style": "Fusion",
            # Zero Two Dark Rose Theme (dark)
            "palette": lambda: manager.create_palette("#310f0f", "#310f0f", "#efefef", "#300d0e", "#531e1e66", "#efefef"),
        },
        "zero-two-dark-theme": {
            "style": "Fusion",
            # Zero Two Dark Theme (dark)
            "palette": lambda: manager.create_palette("#310f0f", "#310f0f", "#efefef", "#300d0e", "#531e1e66", "#efefef"),
        },
        "zero-two-light-lily-theme": {
            "style": "Fusion",
            # Zero Two Light Lily Theme (light)
            "palette": lambda: manager.create_palette("#fcfcfc", "#fcfcfc", "#252427", "#fafafa", "#e9b4b855", "#252427"),
        },
        "zero-two-light-sakura-theme": {
            "style": "Fusion",
            # Zero Two Light Sakura Theme (light)
            "palette": lambda: manager.create_palette("#ffe6ee", "#ffe6ee", "#252427", "#ffe5ef", "#c1e9d4", "#252427"),
        },
        "zero-two-light-theme": {
            "style": "Fusion",
            # Zero Two Light Theme (light)
            "palette": lambda: manager.create_palette("#fcfcfc", "#fcfcfc", "#252427", "#fafafa", "#e9b4b855", "#252427"),
        },
        "bridge": {
            "style": "Fusion",
            # Bridge (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "colors": {
            "style": "Fusion",
            # Colors (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "complete_dark": {
            "style": "Fusion",
            # Complete Dark (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "complete_light": {
            "style": "Fusion",
            # Complete Light (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "darcula-pycharm-dark-gui-color-theme": {
            "style": "Fusion",
            # Darcula Pycharm Dark Gui Color Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "darcula-pycharm-light-gui-color-theme": {
            "style": "Fusion",
            # Darcula Pycharm Light Gui Color Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "dark_plus": {
            "style": "Fusion",
            # Dark Plus (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "default2": {
            "style": "Fusion",
            # Default2 (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "defaulttheme": {
            "style": "Fusion",
            # Defaulttheme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-dark-bold": {
            "style": "Fusion",
            # Eva Dark Bold (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-dark-italic-bold": {
            "style": "Fusion",
            # Eva Dark Italic Bold (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-dark-italic": {
            "style": "Fusion",
            # Eva Dark Italic (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-dark": {
            "style": "Fusion",
            # Eva Dark (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-light-bold": {
            "style": "Fusion",
            # Eva Light Bold (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-light-italic-bold": {
            "style": "Fusion",
            # Eva Light Italic Bold (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-light-italic": {
            "style": "Fusion",
            # Eva Light Italic (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "eva-light": {
            "style": "Fusion",
            # Eva Light (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "jellyfish-theme-color-theme": {
            "style": "Fusion",
            # Jellyfish Theme Color Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "light_plus": {
            "style": "Fusion",
            # Light Plus (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-classic-icon-theme": {
            "style": "Fusion",
            # Monokai Classic Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-classic-monochrome-icon-theme": {
            "style": "Fusion",
            # Monokai Classic Monochrome Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-machine-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Machine Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-machine-monochrome-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Machine Monochrome Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-octagon-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Octagon Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-octagon-monochrome-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Octagon Monochrome Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-ristretto-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Ristretto Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-ristretto-monochrome-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Ristretto Monochrome Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-spectrum-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Spectrum Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-filter-spectrum-monochrome-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Filter Spectrum Monochrome Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "monokai-pro-monochrome-icon-theme": {
            "style": "Fusion",
            # Monokai Pro Monochrome Icon Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "vue-theme-color-theme-high-contrast": {
            "style": "Fusion",
            # Vue Theme Color Theme High Contrast (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "vue-theme-color-theme": {
            "style": "Fusion",
            # Vue Theme Color Theme (dark)
            "palette": lambda: manager.create_palette("#1E1E1E", "#1E1E1E", "#FFFFFF", "#1E1E1E", "#0078D4", "#FFFFFF"),
        },
        "template": {
            "style": "Fusion",
            # Template: Solarized Dark based theme from template.json
            # Primary: #003847 (input.background), Secondary: #00212b (sideBar.background)
            # Text: #93a1a1, Highlight: #2aa198 (teal accent), Bright: #d6dbdb
            "palette": lambda: manager.create_palette("#003847", "#00212b", "#93a1a1", "#004052", "#2aa198", "#d6dbdb"),
        },
    }
    return configs
