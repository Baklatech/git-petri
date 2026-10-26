"""Half-block canvas: the same dish drawn in solid, shaded pixels, the way tuigler and
filepile draw their sprites. Each cell is two square pixels, ▀ over ▄, so a pixel spans
2 x 2 of the braille sub-pixels the simulation works in."""

import random
from math import atan2, cos, sin, sqrt

from .render import BG, TAU, Renderer
from .theme import mix, pack


class Blocks(Renderer):
    def retheme(self):
        super().retheme()
        rim, specks = set(), set()
        cx, cy, a, b = self.cx / 2, self.cy / 2, self.A / 2, self.B / 2
        steps = int(7 * max(a, b))
        for k in range(steps):
            ang = TAU * k / steps
            rim.add(self._at(cx + a * cos(ang), cy + b * sin(ang)))
        rng = random.Random(5)
        for _ in range(int(a * b / 500)):  # a pixel here is four dots: fewer, or it is grit
            ang, rad = rng.uniform(0, TAU), sqrt(rng.random()) * 0.96
            specks.add(self._at(cx + a * rad * cos(ang), cy + b * rad * sin(ang)))
        rim.discard(-1)
        specks.discard(-1)
        self.rim, self.specks = sorted(rim), sorted(specks - rim)

    def _at(self, x, y):
        X, Y = int(x), int(y)
        return Y * self.W + X if 0 <= X < self.W and 0 <= Y < 2 * self.H else -1

    # -- primitives, in sub-pixel coordinates like the braille ones ----------

    def begin(self):
        self.txt = {}
        self.me = 0
        self.panel = self.link = None
        pix = self.pix = [-1] * (2 * self.W * self.H)
        th = self.theme
        c = pack(mix(th.bg, th.speck, 0.7))
        for i in self.specks:
            pix[i] = c
        c = pack(mix(th.bg, th.rim, 0.6))
        for i in self.rim:
            pix[i] = c

    def dot(self, X, Y, c):
        if 0 <= X < self.W and 0 <= Y < 2 * self.H:
            self.pix[Y * self.W + X] = c

    def px(self, x, y, c, me):
        self.dot(x >> 1, y >> 1, c)

    def line(self, x0, y0, x1, y1, c, step, phase):
        # Solid, not dotted: a pixel is already coarse enough to read as a thread.
        x0, y0, x1, y1 = x0 / 2, y0 / 2, x1 / 2, y1 / 2
        n = int(max(abs(x1 - x0), abs(y1 - y0)))
        for k in range(n + 1):
            f = k / n if n else 0.0
            self.dot(int(x0 + (x1 - x0) * f), int(y0 + (y1 - y0) * f), c)

    def ring(self, cx, cy, rad, c):
        cx, cy, rad = cx / 2, cy / 2, rad / 2
        n = max(8, int(rad * 7))
        for k in range(n):
            a = TAU * k / n
            self.dot(int(cx + rad * cos(a)), int(cy + rad * sin(a)), c)

    def disc(self, cx, cy, r, c, diamond=False):
        cx, cy, r = cx / 2, cy / 2, max(0.5, r / 2)
        hi = pack(mix(unpack(c), self.theme.bright, 0.3)) if r >= 1.5 else c
        X0, Y0 = int(cx - r), int(cy - r)
        hit = False
        for Y in range(Y0, int(cy + r) + 1):
            dy = Y + 0.5 - cy
            for X in range(X0, int(cx + r) + 1):
                dx = X + 0.5 - cx
                if (abs(dx) + abs(dy) > r) if diamond else (dx * dx + dy * dy > r * r):
                    continue
                hit = True
                self.dot(X, Y, hi if dx + dy < -r * 0.6 else c)
        if not hit:  # smaller than a pixel: still one pixel, never nothing
            self.dot(int(cx), int(cy), c)

    def blob(self, cx, cy, r, shades, t, seed, lobes, dens):
        """A colony as one solid, wobbly body: dim at the rim, full in the middle, with
        a highlight up and to the left like filepile's junk."""
        cx, cy, r = cx / 2, cy / 2, r / 2
        amp = 0.09
        reach = r * (1 + 2 * amp)
        inv = 1.0 / (r * r)
        ph, ph2 = float(seed), seed * 1.7
        gain = dens * 9
        glint = pack(mix(unpack(shades[8]), self.theme.bright, 0.35))
        gx, gy, gr = cx - r * 0.35, cy - r * 0.4, (r * 0.22) ** 2
        for Y in range(int(cy - reach), int(cy + reach) + 1):
            dy = Y + 0.5 - cy
            for X in range(int(cx - reach), int(cx + reach) + 1):
                dx = X + 0.5 - cx
                q = (dx * dx + dy * dy) * inv
                if q >= 1.45:
                    continue
                a = atan2(dy, dx)
                wob = 1 + amp * sin(lobes * a + ph) + amp * 0.6 * sin((lobes + 2) * a + ph2)
                q /= wob * wob
                if q >= 1:
                    continue
                k = min(8, 3 + int((1 - q) * gain))
                if q > 0.8:
                    k = 2  # a darker membrane keeps touching colonies apart
                ex, ey = X + 0.5 - gx, Y + 0.5 - gy
                self.dot(X, Y, glint if r >= 3 and ex * ex + ey * ey < gr else shades[k])

    def cell(self, n, cx, cy, r, t):
        """A CI organism: a solid membrane round a tinted interior."""
        th = self.theme
        cx, cy, r = cx / 2, cy / 2, r / 2
        running, failed = n.state == "running", n.state == "failed"
        main = self.ci_colour(n, t)
        wall, inner = pack(main), pack(mix(th.bg, main, 0.35))
        heal = t - n.heal
        front = r * 1.15 * heal / 1.2 if heal < 1.2 else -1.0
        healed, sick = pack(th.bright_green), pack(th.red)
        spike = 0.14 if failed else 0.0
        reach = r * (1 + spike)
        beat = int(t)
        spin, flow, seed = beat * 0.7, beat, n.seed
        for Y in range(int(cy - reach), int(cy + reach) + 1):
            dy = Y + 0.5 - cy
            for X in range(int(cx - reach), int(cx + reach) + 1):
                dx = X + 0.5 - cx
                d = sqrt(dx * dx + dy * dy)
                edge = r * (1 + spike * sin(7 * atan2(dy, dx) + seed)) if failed else r
                if d > edge:
                    continue
                if d >= edge - 1:
                    if running and (atan2(dy, dx) - spin) % TAU > 4.4:
                        continue  # a gap that travels round the membrane
                    c = wall
                elif running and (X + Y * 2 + flow) % 5 == 0:
                    c = wall  # streaming cytoplasm
                else:
                    c = inner
                if front >= 0:
                    c = healed if d < front else sick
                self.dot(X, Y, c)

    # -- output -------------------------------------------------------------

    def compose(self):
        w, pix = self.W, self.pix
        ch, col = [" "] * (w * self.H), [0] * (w * self.H)
        for y in range(self.H):
            top, bot = 2 * y * w, (2 * y + 1) * w
            for x in range(w):
                a, b = pix[top + x], pix[bot + x]
                if a < 0 and b < 0:
                    continue
                i = y * w + x
                if b < 0:
                    ch[i], col[i] = "▀", a
                elif a < 0:
                    ch[i], col[i] = "▄", b
                elif a == b:
                    ch[i], col[i] = "█", a
                else:
                    ch[i], col[i] = "▀", a | BG | b << 27
        for i, (c, k) in self.txt.items():
            ch[i], col[i] = c, k
        return ch, col


def unpack(k):
    return (k >> 16 & 255, k >> 8 & 255, k & 255)
