"""Deterministic, bounded OKLab clustering without an image-processing dependency."""
from collections import Counter
import colorsys
import math


def to_oklab(rgb):
    r, g, b = (c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in rgb)
    l = (.4122214708 * r + .5363325363 * g + .0514459929 * b) ** (1 / 3)
    m = (.2119034982 * r + .6806995451 * g + .1073969566 * b) ** (1 / 3)
    s = (.0883024619 * r + .2817188376 * g + .6299787005 * b) ** (1 / 3)
    return (.2104542553 * l + .7936177850 * m - .0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + .4505937099 * s,
            .0259040371 * l + .7827717662 * m - .8086757660 * s)


def from_oklab(lab):
    light, a, b = lab
    l = (light + .3963377774 * a + .2158037573 * b) ** 3
    m = (light - .1055613458 * a - .0638541728 * b) ** 3
    s = (light - .0894841775 * a - 1.2914855480 * b) ** 3
    linear = (4.0767416621 * l - 3.3077115913 * m + .2309699292 * s,
              -1.2684380046 * l + 2.6097574011 * m - .3413193965 * s,
              -.0041960863 * l - .7034186147 * m + 1.7076147010 * s)
    return tuple(max(0, min(1, 12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055)) for c in linear)


def distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def clusters(samples):
    """Quantize first, then merge nearby perceptual colours into at most 32 clusters."""
    histogram = Counter(tuple(round(c * 31) for c in colorsys.hls_to_rgb((h % 360) / 360, l, s))
                        for h, s, l in samples)
    result = []
    for rgb, count in sorted(histogram.items(), key=lambda item: (-item[1], item[0])):
        lab = to_oklab(tuple(c / 31 for c in rgb))
        nearest = min(range(len(result)), key=lambda i: distance(lab, result[i][0])) if result else None
        if nearest is not None and (distance(lab, result[nearest][0]) < .065 ** 2 or len(result) >= 32):
            previous, weight = result[nearest]
            result[nearest] = (tuple((a * weight + b * count) / (weight + count) for a, b in zip(previous, lab)), weight + count)
        else:
            result.append((lab, count))
    return sorted(result, key=lambda item: (-item[1], item[0]))


def select(samples):
    """Return dominant hue/saturation, accent hue/saturation and a monochrome flag."""
    groups = clusters(samples)
    if not groups:
        return 0, 0, 0, 0, True
    total = sum(count for _, count in groups)
    colourful = [(lab, count) for lab, count in groups
                 if .18 < lab[0] < .94 and math.hypot(lab[1], lab[2]) >= .025]
    mono = sum(count for _, count in colourful) / total < .04
    dominant = groups[0][0]
    dom_h, _, dom_s = colorsys.rgb_to_hls(*from_oklab(dominant))
    if mono or not colourful:
        return dom_h * 360, 0, dom_h * 360, 0, True
    candidates = [(lab, count) for lab, count in colourful if count / total >= .015]
    if not candidates:
        return dom_h * 360, 0, dom_h * 360, 0, True

    def score(item):
        lab, count = item
        return math.sqrt(count / total) * math.hypot(lab[1], lab[2])

    main = max(candidates, key=score)
    pops = [item for item in candidates if item[1] / total >= .025
            and distance(item[0][1:], main[0][1:]) >= .09 ** 2
            and score(item) >= score(main) * .35]
    accent = max(pops, key=score) if pops else main
    acc_h, _, acc_s = colorsys.rgb_to_hls(*from_oklab(accent[0]))
    return dom_h * 360, dom_s, acc_h * 360, min(acc_s, .92), False
