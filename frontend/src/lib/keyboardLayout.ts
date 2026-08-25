// Physical QWERTY layout for the keyboard heatmap: (row x-offset in key
// units, [(base char, shifted char or null), ...] left to right). Ported
// from generate_dashboard.py's KEYBOARD_ROWS. Offsets approximate real key
// stagger, just enough for the heatmap to read as a keyboard.
export type KeyDef = readonly [base: string, shifted: string | null]

export const KEYBOARD_ROWS: ReadonlyArray<readonly [number, readonly KeyDef[]]> = [
  [0.0, [['`', '~'], ['1', '!'], ['2', '@'], ['3', '#'], ['4', '$'], ['5', '%'],
    ['6', '^'], ['7', '&'], ['8', '*'], ['9', '('], ['0', ')'], ['-', '_'], ['=', '+']]],
  [0.5, [['q', null], ['w', null], ['e', null], ['r', null], ['t', null], ['y', null],
    ['u', null], ['i', null], ['o', null], ['p', null], ['[', '{'], [']', '}'], ['\\', '|']]],
  [0.75, [['a', null], ['s', null], ['d', null], ['f', null], ['g', null], ['h', null],
    ['j', null], ['k', null], ['l', null], [';', ':'], ["'", '"']]],
  [1.25, [['z', null], ['x', null], ['c', null], ['v', null], ['b', null], ['n', null],
    ['m', null], [',', '<'], ['.', '>'], ['/', '?']]],
]

export const SPACE_KEY = ' '
export const SPACE_ROW_OFFSET = 4.625
export const SPACE_WIDTH_UNITS = 6.25
