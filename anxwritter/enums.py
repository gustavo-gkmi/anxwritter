"""
Enumerations and constants for i2 Analyst's Notebook entities, links and attributes.

All enum values use short lowercase names. The builder translates them to the
full PascalCase ANB XML strings at the emission boundary via ``_resolve_enum()``.
"""
from enum import Enum


class Representation(str, Enum):
    """Visual representation type for an entity.

    Values are lowercase strings. The builder maps them to full PascalCase
    ANB XML representation names (e.g. 'icon' → 'RepresentAsIcon').
    """
    ICON = 'icon'
    THEME_LINE = 'theme_line'
    EVENT_FRAME = 'event_frame'
    BOX = 'box'
    CIRCLE = 'circle'
    TEXT_BLOCK = 'text_block'
    LABEL = 'label'
    OLE_OBJECT = 'ole_object'  # not yet implemented — falls back to Icon


class ArrowStyle(str, Enum):
    """Direction of a link arrow.

    Also accepts symbol aliases: ``'->'``, ``'<-'``, ``'<->'``.
    """
    ARROW_ON_HEAD = 'head'    # source → destination
    ARROW_ON_TAIL = 'tail'    # destination → source
    ARROW_ON_BOTH = 'both'    # bidirectional


class AttributeType(str, Enum):
    """Data type of an entity or link attribute.

    Values are lowercase strings. The builder maps them to ANX XML type names
    (e.g. 'text' → 'AttText').
    """
    TEXT = 'text'
    FLAG = 'flag'
    DATETIME = 'datetime'
    NUMBER = 'number'


class Multiplicity(str, Enum):
    """How multiple links between the same entity pair are displayed.

    Set via the ``multiplicity`` field on ``Link``.
    All links between the same entity pair must use the same value.
    """
    MULTIPLE = 'multiple'   # each link is a separate arc (default)
    SINGLE   = 'single'     # all links collapse into one with a card stack
    DIRECTED = 'directed'   # directional grouping (schema-valid, untested)


class ThemeWiring(str, Enum):
    """How a theme line behaves after passing through an event frame connection.

    Set via the ``theme_wiring`` field on ``Link``.
    Only relevant for ThemeLine↔EventFrame connections.
    """
    KEEPS_AT_EVENT_HEIGHT    = 'keep_event'      # stays at event frame height
    RETURNS_TO_THEME_HEIGHT  = 'return_theme'    # returns to original theme height
    GOES_TO_NEXT_EVENT       = 'next_event'      # changes to next event frame height
    NO_DIVERSION             = 'no_diversion'    # theme line passes straight through


class MergeBehaviour(str, Enum):
    """Attribute merge/paste behaviour values.

    Used for ``merge_behaviour`` and ``paste_behaviour`` on ``AttributeClass``.

    All types (merge + paste):
        assign  — replace with incoming value ("pasted value")
        noop    — keep existing, ignore incoming ("existing value")

    Text (merge + paste):
        add             — concatenate without separator
        add_space       — concatenate with a space
        add_line_break  — concatenate with a line break

    Number (merge: add/max/min only; paste: all five):
        add            — sum of both values
        max            — keep the higher value
        min            — keep the lower value
        subtract       — existing minus pasted
        subtract_swap  — pasted minus existing

    DateTime (merge + paste):
        min — keep the earlier timestamp
        max — keep the later timestamp

    Flag (merge + paste):
        or   — boolean OR
        and  — boolean AND
        xor  — boolean XOR
    """
    ASSIGN              = 'assign'
    NO_OP               = 'noop'
    ADD                 = 'add'
    ADD_WITH_SPACE      = 'add_space'
    ADD_WITH_LINE_BREAK = 'add_line_break'
    MAX                 = 'max'
    MIN                 = 'min'
    SUBTRACT            = 'subtract'
    SUBTRACT_SWAP       = 'subtract_swap'
    OR                  = 'or'
    AND                 = 'and'
    XOR                 = 'xor'


class Enlargement(str, Enum):
    """Icon enlargement (size) for Icon, EventFrame, and ThemeLine entities."""
    HALF      = 'half'
    SINGLE    = 'single'
    DOUBLE    = 'double'
    TRIPLE    = 'triple'
    QUADRUPLE = 'quadruple'


class DotStyle(str, Enum):
    """Line dash/dot pattern for a Strength entry.

    Also accepts symbol aliases: ``'-'``, ``'---'``, ``'-.'``, ``'-..'``, ``'...'``.
    """
    SOLID        = 'solid'
    DASHED       = 'dashed'
    DASH_DOT     = 'dash_dot'
    DASH_DOT_DOT = 'dash_dot_dot'
    DOTTED       = 'dotted'



class Color(str, Enum):
    """All 40 named colors accepted by i2 ANB.

    Values are lowercase snake_case (e.g. ``BLUE = 'blue'``,
    ``LIGHT_ORANGE = 'light_orange'``). The builder normalizes input
    (Title Case, lowercase, hyphens, spaces, hex, COLORREF int) via
    ``colors.color_to_colorref``.
    """
    BLACK            = 'black'
    BROWN            = 'brown'
    OLIVE_GREEN      = 'olive_green'
    DARK_GREEN       = 'dark_green'
    DARK_TEAL        = 'dark_teal'
    DARK_BLUE        = 'dark_blue'
    INDIGO           = 'indigo'
    DARK_GREY        = 'dark_grey'
    DARK_RED         = 'dark_red'
    ORANGE           = 'orange'
    DARK_YELLOW      = 'dark_yellow'
    GREEN            = 'green'
    TEAL             = 'teal'
    BLUE             = 'blue'
    BLUE_GREY        = 'blue_grey'
    GREY             = 'grey'
    RED              = 'red'
    LIGHT_ORANGE     = 'light_orange'
    LIME             = 'lime'
    SEA_GREEN        = 'sea_green'
    AQUA             = 'aqua'
    LIGHT_BLUE       = 'light_blue'
    VIOLET           = 'violet'
    LIGHT_GREY       = 'light_grey'
    PINK             = 'pink'
    GOLD             = 'gold'
    YELLOW           = 'yellow'
    BRIGHT_GREEN     = 'bright_green'
    TURQUOISE        = 'turquoise'
    SKY_BLUE         = 'sky_blue'
    PLUM             = 'plum'
    SILVER           = 'silver'
    ROSE             = 'rose'
    TAN              = 'tan'
    LIGHT_YELLOW     = 'light_yellow'
    LIGHT_GREEN      = 'light_green'
    LIGHT_TURQUOISE  = 'light_turquoise'
    PALE_BLUE        = 'pale_blue'
    LAVENDER         = 'lavender'
    WHITE            = 'white'


class LegendItemType(str, Enum):
    """Type of a row in the chart legend.

    Set via ``LegendItem.item_type``. Values are lowercase strings.
    The builder maps them to ANB XML names like ``LegendItemTypeFont``.
    """
    FONT       = 'font'
    TEXT       = 'text'
    ICON       = 'icon'
    ATTRIBUTE  = 'attribute'
    LINE       = 'line'
    LINK       = 'link'
    TIMEZONE   = 'timezone'
    ICON_FRAME = 'icon_frame'


#: All valid shading color names accepted by i2 ANB (40 colors).
VALID_SHADING_COLORS: frozenset = frozenset([
    'Black', 'Brown', 'Olive Green', 'Dark Green', 'Dark Teal', 'Dark Blue',
    'Indigo', 'Dark Grey', 'Dark Red', 'Orange', 'Dark Yellow', 'Green',
    'Teal', 'Blue', 'Blue-Grey', 'Grey', 'Red', 'Light Orange', 'Lime',
    'Sea Green', 'Aqua', 'Light Blue', 'Violet', 'Light Grey', 'Pink',
    'Gold', 'Yellow', 'Bright Green', 'Turquoise', 'Sky Blue', 'Plum',
    'Silver', 'Rose', 'Tan', 'Light Yellow', 'Light Green',
    'Light Turquoise', 'Pale Blue', 'Lavender', 'White',
])
