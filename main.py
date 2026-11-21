#!/usr/bin/env python3
"""Poster for a place that is not there.

Paints a travel poster for Aurelia, an island that never existed:
a dusk sky, a low sun, isles drifting over a teal sea, an airship,
and a title band. Only the standard library is used (zlib and struct
build the PNG by hand); nothing is fetched from the network.
The program writes a 1024 by 1024 PNG to /output/entry.png.
"""

import os
import struct
import zlib

SIZE = 1024
STARS = 140
STREAKS = 46

# Seven rows of five bits per letter, top row first.
GLYPHS = {
    'A': ('01110', '10001', '10001', '11111', '10001', '10001', '10001'),
    'B': ('11110', '10001', '10001', '11110', '10001', '10001', '11110'),
    'C': ('01110', '10001', '10000', '10000', '10000', '10001', '01110'),
    'D': ('11110', '10001', '10001', '10001', '10001', '10001', '11110'),
    'E': ('11111', '10000', '10000', '11110', '10000', '10000', '11111'),
    'F': ('11111', '10000', '10000', '11110', '10000', '10000', '10000'),
    'G': ('01110', '10001', '10000', '10111', '10001', '10001', '01111'),
    'H': ('10001', '10001', '10001', '11111', '10001', '10001', '10001'),
    'I': ('01110', '00100', '00100', '00100', '00100', '00100', '01110'),
    'K': ('10001', '10010', '10100', '11000', '10100', '10010', '10001'),
    'L': ('10000', '10000', '10000', '10000', '10000', '10000', '11111'),
    'M': ('10001', '11011', '10101', '10101', '10001', '10001', '10001'),
    'N': ('10001', '11001', '10101', '10011', '10001', '10001', '10001'),
    'O': ('01110', '10001', '10001', '10001', '10001', '10001', '01110'),
    'P': ('11110', '10001', '10001', '11110', '10000', '10000', '10000'),
    'R': ('11110', '10001', '10001', '11110', '10100', '10010', '10001'),
    'S': ('01111', '10000', '10000', '01110', '00001', '00001', '11110'),
    'T': ('11111', '00100', '00100', '00100', '00100', '00100', '00100'),
    'U': ('10001', '10001', '10001', '10001', '10001', '10001', '01110'),
    'V': ('10001', '10001', '10001', '10001', '10001', '01010', '00100'),
    'W': ('10001', '10001', '10001', '10101', '10101', '11011', '10001'),
    'Y': ('10001', '10001', '01010', '00100', '00100', '00100', '00100'),
    '0': ('01110', '10001', '10011', '10101', '11001', '10001', '01110'),
    '1': ('00100', '01100', '00100', '00100', '00100', '00100', '01110'),
    '2': ('01110', '10001', '00001', '00110', '01000', '10000', '11111'),
    '4': ('00010', '00110', '01010', '10010', '11111', '00010', '00010'),
    '9': ('01110', '10001', '10001', '01111', '00001', '00001', '01110'),
    '.': ('00000', '00000', '00000', '00000', '00000', '01100', '01100'),
    '-': ('00000', '00000', '00000', '01110', '00000', '00000', '00000'),
    ' ': ('00000', '00000', '00000', '00000', '00000', '00000', '00000'),
}


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def randseq(seed):
    while True:
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        yield seed


class Board:
    def __init__(self, side):
        self.w = side
        self.h = side
        self.px = bytearray(side * side * 3)

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def mixp(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            for k in range(3):
                self.px[i + k] = int(self.px[i + k] * (1 - a) + c[k] * a)

    def box(self, x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.put(x, y, c)

    def sky(self, y0, y1, stops):
        # stops hold (position, colour) pairs; one colour per row.
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0 - 1)
            for i in range(len(stops) - 1):
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                if t0 <= t <= t1:
                    self.box(0, y, self.w, y + 1, mix(c0, c1, (t - t0) / (t1 - t0)))
                    break

    def disc(self, cx, cy, r, c, alpha=1.0):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    if alpha >= 1.0:
                        self.put(x, y, c)
                    else:
                        self.mixp(x, y, c, alpha)

    def oval(self, cx, cy, rx, ry, c, alpha=1.0):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    if alpha >= 1.0:
                        self.put(x, y, c)
                    else:
                        self.mixp(x, y, c, alpha)

    def tri(self, x0, y0, x1, y1, x2, y2, c):
        # Scanline fill: walk each row between the sorted corners.
        pts = sorted([(x0, y0), (x1, y1), (x2, y2)], key=lambda p: p[1])
        (ax, ay), (bx, by), (cx, cy) = pts
        for y in range(ay, cy + 1):
            if y < by:
                t1 = (y - ay) / max(1, by - ay)
                xa = ax + (bx - ax) * t1
            else:
                xa = bx
            t2 = (y - ay) / max(1, cy - ay)
            xb = ax + (cx - ax) * t2
            if xa > xb:
                xa, xb = xb, xa
            for x in range(int(xa), int(xb) + 1):
                self.put(x, y, c)

    def hline(self, x0, x1, y, c, alpha=1.0):
        for x in range(x0, x1 + 1):
            if alpha >= 1.0:
                self.put(x, y, c)
            else:
                self.mixp(x, y, c, alpha)

    def vline(self, x, y0, y1, c, alpha=1.0):
        for y in range(y0, y1 + 1):
            if alpha >= 1.0:
                self.put(x, y, c)
            else:
                self.mixp(x, y, c, alpha)

    def glyphs(self, s, x, y, scale, c):
        for ch in s:
            rows = GLYPHS.get(ch, GLYPHS[' '])
            for row in range(7):
                for col in range(5):
                    if rows[row][col] == '1':
                        self.box(x + col * scale, y + row * scale,
                                 x + (col + 1) * scale, y + (row + 1) * scale, c)
            x += 6 * scale

    def text_w(self, s, scale):
        return len(s) * 6 * scale - scale

    def text_centered(self, s, y, scale, c):
        self.glyphs(s, (self.w - self.text_w(s, scale)) // 2, y, scale, c)


def paint():
    board = Board(SIZE)
    # Dusk: indigo, then violet, orange, gold.
    board.sky(0, 640, [(0.0, (24, 36, 96)), (0.45, (88, 58, 138)),
                       (0.8, (232, 110, 70)), (1.0, (255, 196, 110))])
    # Stars scattered over the upper sky.
    rng = randseq(2149)
    for _ in range(STARS):
        r = next(rng)
        x = r % SIZE
        y = (r >> 9) % 300
        b = 150 + (r >> 17) % 105
        board.put(x, y, (b, b, min(255, b + 20)))
    # Sun, ringed by a soft glow.
    for r, a in ((150, 0.12), (120, 0.18), (100, 0.35)):
        board.disc(512, 600, r, (255, 214, 120), a)
    board.disc(512, 600, 88, (255, 222, 130))
    # Distant ridge.
    for x0, y0, x1, y1, x2, y2 in [
            (0, 640, 150, 520, 320, 640), (220, 640, 420, 500, 640, 640),
            (520, 640, 700, 540, 900, 640), (800, 640, 950, 510, 1024, 640)]:
        board.tri(x0, y0, x1, y1, x2, y2, (52, 36, 92))
    # Closer ridge.
    for x0, y0, x1, y1, x2, y2 in [
            (0, 660, 200, 580, 420, 660), (340, 660, 560, 570, 780, 660),
            (680, 660, 880, 590, 1024, 660)]:
        board.tri(x0, y0, x1, y1, x2, y2, (30, 20, 62))
    # Sea below the horizon.
    board.sky(640, 1024, [(0.0, (12, 84, 112)), (1.0, (4, 38, 68))])
    # Shimmering streaks of the sun on the water.
    rng = randseq(777)
    for _ in range(STREAKS):
        r = next(rng)
        y = 650 + (r >> 4) % 360
        wdt = 30 + (r >> 11) % 130
        x0 = 512 - wdt // 2 + ((r >> 7) % 40) - 20
        board.hline(x0, x0 + wdt, y, (255, 190, 110), 0.25 + ((r >> 3) % 40) / 100.0)
    # Drifting isles: dark rock, green crown, falling water.
    for cx, cy, rx, ry in [(210, 300, 130, 34), (790, 250, 150, 38), (560, 170, 95, 26)]:
        board.tri(cx - int(rx * 0.55), cy + 6, cx + int(rx * 0.55), cy + 6,
                  cx, cy + 92, (34, 54, 46))
        board.oval(cx, cy, rx, ry, (46, 78, 60))
        board.oval(cx, cy - 6, rx - 14, 14, (74, 128, 84))
        for dx in (-rx // 3, 0, rx // 3):
            board.vline(cx + dx, cy + 44, cy + 86, (150, 210, 225), 0.85)
    # Airship crossing the sun.
    board.oval(700, 430, 110, 34, (216, 84, 66))
    board.tri(596, 428, 628, 400, 628, 428, (180, 60, 48))
    board.box(672, 462, 728, 478, (60, 44, 40))
    for wx in (650, 680, 710, 740):
        board.box(wx, 424, wx + 12, 436, (255, 240, 190))
    # Title band at the bottom.
    board.box(0, 830, SIZE, SIZE, (14, 18, 46))
    board.hline(0, SIZE - 1, 830, (212, 168, 92))
    board.hline(0, SIZE - 1, 834, (212, 168, 92))
    board.text_centered('VISIT AURELIA', 852, 11, (250, 238, 200))
    board.text_centered('WHERE THE SEA CLIMBS THE SKY', 946, 5, (255, 196, 110))
    board.text_centered('EST. 2149 - THE FLOATING ISLES', 990, 3, (180, 180, 200))
    # Thin gold frame.
    for t in range(3):
        board.box(8 + t, 8 + t, SIZE - 8 - t, 11 + t, (212, 168, 92))
        board.box(8 + t, SIZE - 11 - t, SIZE - 8 - t, SIZE - 8 - t, (212, 168, 92))
        board.box(8 + t, 8 + t, 11 + t, SIZE - 8 - t, (212, 168, 92))
        board.box(SIZE - 11 - t, 8 + t, SIZE - 8 - t, SIZE - 8 - t, (212, 168, 92))
    return board


def save_png(board, path):
    raw = bytearray()
    for y in range(board.h):
        row = bytearray(board.px[y * board.w * 3:(y + 1) * board.w * 3])
        # Sub filter (type 1): each byte less the byte three back.
        filt = bytearray(len(row))
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            filt[i] = (b - left) & 0xFF
        raw.append(1)
        raw.extend(filt)
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        c = struct.pack('>I', len(payload)) + kind + payload
        return c + struct.pack('>I', zlib.crc32(kind + payload) & 0xFFFFFFFF)

    png = b'\x89PNG\r\n\x1a\n'
    png += chunk(b'IHDR', struct.pack('>IIBBBBB', board.w, board.h, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', data)
    png += chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(png)


def main():
    os.makedirs('/output', exist_ok=True)
    path = '/output/entry.png'
    save_png(paint(), path)
    size = os.path.getsize(path)
    if size <= 1024:
        raise SystemExit('entry.png suspiciously small: %d bytes' % size)
    if size > 1048576:
        raise SystemExit('entry.png exceeds the 1 MiB cap: %d bytes' % size)
    with open(path, 'rb') as f:
        head = f.read(8)
    if head != b'\x89PNG\r\n\x1a\n':
        raise SystemExit('entry.png is not a PNG')
    with open(path, 'rb') as f:
        ihdr = f.read(33)
    w, h = struct.unpack('>II', ihdr[16:24])
    if (w, h) != (SIZE, SIZE):
        raise SystemExit('entry.png dimensions %dx%d, expected %dx%d' % (w, h, SIZE, SIZE))


main()
