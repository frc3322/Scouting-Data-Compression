"""Shared constants for encoding and decoding."""

import numpy as np

DATA_COLOR_SEQUENCE: tuple[tuple[int, int, int], ...] = (
    (0, 0, 255),
    (0, 255, 0),
    (255, 0, 0),
    (0, 0, 0),
)

DATA_COLOR_MAP: dict[int, tuple[int, int, int]] = dict(enumerate(DATA_COLOR_SEQUENCE))

ALLOWED_COLOR_PALETTE: tuple[tuple[int, int, int], ...] = DATA_COLOR_SEQUENCE + (
    (255, 255, 255),
)

PALETTE_COLORS: np.ndarray = np.array(ALLOWED_COLOR_PALETTE, dtype=np.uint8)
PALETTE_COLOR_ARRAY: np.ndarray = PALETTE_COLORS.astype(np.int16)
WHITE_COLOR: np.ndarray = np.array((255, 255, 255), dtype=np.int16)
WHITE_INDEX: int = int(
    np.nonzero(np.all(PALETTE_COLOR_ARRAY == WHITE_COLOR, axis=1))[0][0]
)
NON_WHITE_INDICES: np.ndarray = np.delete(np.arange(len(PALETTE_COLORS)), WHITE_INDEX)
NON_WHITE_PALETTE: np.ndarray = PALETTE_COLOR_ARRAY[NON_WHITE_INDICES]
NON_WHITE_PALETTE_FLOAT: np.ndarray = NON_WHITE_PALETTE.astype(np.float32)
