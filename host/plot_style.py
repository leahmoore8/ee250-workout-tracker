"""Exact six circular swatches from Leah's screenshot, converted to sRGB.
AI assistance: Developed with OpenAI Codex.
"""
CORAL = '#ff7651'
ROSE = '#f25d71'
PINK = '#d2528d'
PURPLE = '#6d56a0'
BLUE = '#295494'
PLUM = '#a4529d'
BACKGROUND = '#fcfafc'
TEXT = '#303344'
MUTED = '#aaa4b5'


def apply_style(plt):
    plt.rcParams.update({
        'figure.facecolor': BACKGROUND,
        'axes.facecolor': '#ffffff',
        'savefig.facecolor': BACKGROUND,
        'text.color': TEXT,
        'axes.labelcolor': TEXT,
        'xtick.color': TEXT,
        'ytick.color': TEXT,
        'axes.edgecolor': '#d8d3df',
        'axes.spines.top': False,
        'axes.spines.right': False,
        'grid.color': '#e8e3ed',
        'axes.titlepad': 16,
        'legend.edgecolor': '#e8e3ed',
        'legend.facecolor': '#ffffff',
        'font.family': 'DejaVu Sans',
    })
