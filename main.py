#!/usr/bin/env python3
"""The Poster for a Place That Isn't There.

Draws a travel poster for Aurelia, a place that does not exist: a
sunset sky, a low sun, floating isles above a teal sea, and a title
band. Pure standard library (zlib + struct for the PNG); no network.
Writes a 1024x1024 PNG to /output/entry.png.
"""

import os
import struct
import zlib

W = 1024
H = 1024

# 5x7 bitmap font: each glyph is 7 rows of 5 bits.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
}


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def blend(self, x, y, c, a):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            for k in range(3):
                self.px[i + k] = int(self.px[i + k] * (1 - a) + c[k] * a)

    def rect(self, x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(self.h, y1)):
            for x in range(max(0, x0), min(self.w, x1)):
                self.set(x, y, c)

    def vgrad(self, y0, y1, stops):
        # stops: list of (t, color); vertical gradient, row-constant.
        for y in range(y0, y1):
            t = (y - y0) / max(1, y1 - y0 - 1)
            for i in range(len(stops) - 1):
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                if t0 <= t <= t1:
                    self.rect(0, y, self.w, y + 1, lerp(c0, c1, (t - t0) / (t1 - t0)))
                    break

    def disc(self, cx, cy, r, c, alpha=1.0):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    if alpha >= 1.0:
                        self.set(x, y, c)
                    else:
                        self.blend(x, y, c, alpha)

    def ellipse(self, cx, cy, rx, ry, c, alpha=1.0):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    if alpha >= 1.0:
                        self.set(x, y, c)
                    else:
                        self.blend(x, y, c, alpha)

    def triangle(self, x0, y0, x1, y1, x2, y2, c):
        # Filled triangle by scanline.
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
                self.set(x, y, c)

    def hline(self, x0, x1, y, c, alpha=1.0):
        for x in range(x0, x1 + 1):
            if alpha >= 1.0:
                self.set(x, y, c)
            else:
                self.blend(x, y, c, alpha)

    def vline(self, x, y0, y1, c, alpha=1.0):
        for y in range(y0, y1 + 1):
            if alpha >= 1.0:
                self.set(x, y, c)
            else:
                self.blend(x, y, c, alpha)

    def text(self, s, x, y, scale, c):
        for ch in s:
            glyph = FONT.get(ch, FONT[" "])
            for row in range(7):
                for col in range(5):
                    if glyph[row][col] == "1":
                        self.rect(x + col * scale, y + row * scale,
                                  x + (col + 1) * scale, y + (row + 1) * scale, c)
            x += 6 * scale

    def text_width(self, s, scale):
        return len(s) * 6 * scale - scale

    def text_centred(self, s, y, scale, c):
        self.text(s, (self.w - self.text_width(s, scale)) // 2, y, scale, c)


def lcg(seed):
    while True:
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        yield seed


def draw():
    cv = Canvas(W, H)
    # Sky: indigo -> violet -> orange -> gold.
    cv.vgrad(0, 640, [(0.0, (24, 36, 96)), (0.45, (88, 58, 138)),
                      (0.8, (232, 110, 70)), (1.0, (255, 196, 110))])
    # Stars in the upper sky.
    rnd = lcg(2149)
    for _ in range(140):
        r = next(rnd)
        x = r % W
        y = (r >> 9) % 300
        b = 150 + (r >> 17) % 105
        cv.set(x, y, (b, b, min(255, b + 20)))
    # Sun with glow.
    for r, a in ((150, 0.12), (120, 0.18), (100, 0.35)):
        cv.disc(512, 600, r, (255, 214, 120), a)
    cv.disc(512, 600, 88, (255, 222, 130))
    # Far mountain ridge.
    for x0, y0, x1, y1, x2, y2 in [
            (0, 640, 150, 520, 320, 640), (220, 640, 420, 500, 640, 640),
            (520, 640, 700, 540, 900, 640), (800, 640, 950, 510, 1024, 640)]:
        cv.triangle(x0, y0, x1, y1, x2, y2, (52, 36, 92))
    # Near ridge.
    for x0, y0, x1, y1, x2, y2 in [
            (0, 660, 200, 580, 420, 660), (340, 660, 560, 570, 780, 660),
            (680, 660, 880, 590, 1024, 660)]:
        cv.triangle(x0, y0, x1, y1, x2, y2, (30, 20, 62))
    # Sea.
    cv.vgrad(640, 1024, [(0.0, (12, 84, 112)), (1.0, (4, 38, 68))])
    # Sun reflection streaks.
    rnd = lcg(777)
    for _ in range(46):
        r = next(rnd)
        y = 650 + (r >> 4) % 360
        wdt = 30 + (r >> 11) % 130
        x0 = 512 - wdt // 2 + ((r >> 7) % 40) - 20
        cv.hline(x0, x0 + wdt, y, (255, 190, 110), 0.25 + ((r >> 3) % 40) / 100.0)
    # Floating isles: dark rock + green top + waterfall.
    for cx, cy, rx, ry in [(210, 300, 130, 34), (790, 250, 150, 38), (560, 170, 95, 26)]:
        cv.triangle(cx - int(rx * 0.55), cy + 6, cx + int(rx * 0.55), cy + 6,
                    cx, cy + 92, (34, 54, 46))
        cv.ellipse(cx, cy, rx, ry, (46, 78, 60))
        cv.ellipse(cx, cy - 6, rx - 14, 14, (74, 128, 84))
        for dx in (-rx // 3, 0, rx // 3):
            cv.vline(cx + dx, cy + 44, cy + 86, (150, 210, 225), 0.85)
    # Airship.
    cv.ellipse(700, 430, 110, 34, (216, 84, 66))
    cv.triangle(596, 428, 628, 400, 628, 428, (180, 60, 48))
    cv.rect(672, 462, 728, 478, (60, 44, 40))
    for wx in (650, 680, 710, 740):
        cv.rect(wx, 424, wx + 12, 436, (255, 240, 190))
    # Title band.
    cv.rect(0, 830, W, H, (14, 18, 46))
    cv.hline(0, W - 1, 830, (212, 168, 92))
    cv.hline(0, W - 1, 834, (212, 168, 92))
    cv.text_centred("VISIT AURELIA", 852, 11, (250, 238, 200))
    cv.text_centred("WHERE THE SEA CLIMBS THE SKY", 946, 5, (255, 196, 110))
    cv.text_centred("EST. 2149 - THE FLOATING ISLES", 990, 3, (180, 180, 200))
    # Gold frame.
    for t in range(3):
        cv.rect(8 + t, 8 + t, W - 8 - t, 11 + t, (212, 168, 92))
        cv.rect(8 + t, H - 11 - t, W - 8 - t, H - 8 - t, (212, 168, 92))
        cv.rect(8 + t, 8 + t, 11 + t, H - 8 - t, (212, 168, 92))
        cv.rect(W - 11 - t, 8 + t, W - 8 - t, H - 8 - t, (212, 168, 92))
    return cv


def write_png(cv, path):
    raw = bytearray()
    for y in range(cv.h):
        row = bytearray(cv.px[y * cv.w * 3:(y + 1) * cv.w * 3])
        # Sub filter (type 1): each byte minus the byte 3 positions back.
        filt = bytearray(len(row))
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            filt[i] = (b - left) & 0xFF
        raw.append(1)
        raw.extend(filt)
    data = zlib.compress(bytes(raw), 9)

    def chunk(kind, payload):
        c = struct.pack(">I", len(payload)) + kind + payload
        return c + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", data)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    os.makedirs("/output", exist_ok=True)
    path = "/output/entry.png"
    write_png(draw(), path)
    size = os.path.getsize(path)
    if size > 1048576:
        raise SystemExit("entry.png exceeds the 1 MiB cap: %d bytes" % size)
    with open(path, "rb") as f:
        head = f.read(8)
    if head != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("entry.png is not a PNG")
    with open(path, "rb") as f:
        ihdr = f.read(33)
    w, h = struct.unpack(">II", ihdr[16:24])
    if (w, h) != (W, H):
        raise SystemExit("entry.png dimensions %dx%d, expected %dx%d" % (w, h, W, H))


if __name__ == "__main__":
    main()
