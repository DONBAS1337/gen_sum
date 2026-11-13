# -*- coding: utf-8 -*-
"""Hit areas for the classic 1920x1080 gen_assets/maps/map_bg.jpg.

The extended map_default.png has a different layout and must not use these.
Unlabelled rooms and invented landmarks remain reachable through the place list.
"""
from __future__ import unicode_literals

CLASSIC_HOTSPOTS = (
    ("gate", (432, 475, 103, 36)),
    ("parking", (286, 443, 128, 108)),
    ("clubs", (434, 516, 132, 84)),
    ("clubhouse", (550, 438, 98, 69)),
    ("music", (623, 256, 76, 83)),
    ("stage", (1061, 58, 85, 81)),
    ("outdoor_stage", (1090, 141, 68, 49)),
    ("forest", (556, 65, 140, 101)),
    ("forest_path", (701, 90, 80, 36)),
    ("library", (1163, 280, 125, 79)),
    ("administration", (774, 345, 102, 106)),
    ("square", (888, 368, 114, 174)),
    ("infirmary", (1041, 355, 88, 90)),
    ("washrooms", (565, 359, 63, 51)),
    ("showers", (696, 438, 94, 58)),
    ("kitchen", (1022, 458, 113, 49)),
    ("canteen", (1014, 509, 120, 72)),
    ("storage", (1148, 487, 66, 93)),
    ("volleyball", (1224, 492, 91, 102)),
    ("gym", (1321, 484, 79, 146)),
    ("football", (1403, 478, 173, 145)),
    ("badminton", (1351, 384, 97, 94)),
    ("beach", (1202, 675, 293, 151)),
    ("lake", (1060, 844, 220, 90)),
    ("boathouse", (837, 805, 119, 46)),
    ("pier", (885, 738, 30, 60)),
    ("island", (573, 979, 217, 97)),
    ("island_far", (1057, 1000, 236, 65)),
    ("old_camp", (237, 1004, 110, 76)),
    ("cabins", (856, 247, 65, 31)),
    ("cabins_south", (765, 609, 62, 41)),
)

# Roof centers on map_bg.jpg. Cabin 12 is at the end of the second row.
CLASSIC_CABINS = (
    ("cabin_01", 786, 297), ("cabin_02", 825, 304),
    ("cabin_03", 866, 309), ("cabin_04", 907, 317),
    ("cabin_05", 977, 329), ("cabin_06", 1020, 339),
    ("cabin_07", 812, 233), ("cabin_08", 855, 240),
    ("cabin_09", 920, 253), ("cabin_10", 962, 260),
    ("cabin_11", 1004, 266), ("cabin_12", 1045, 276),
    ("cabin_13", 831, 176), ("cabin_14", 870, 182),
    ("cabin_15", 905, 188), ("cabin_16", 942, 194),
    ("cabin_17", 978, 202), ("cabin_18", 665, 568),
    ("cabin_19", 710, 576), ("cabin_20", 752, 582),
    ("cabin_21", 795, 591), ("cabin_22", 675, 624),
    ("cabin_23", 735, 643), ("cabin_24", 687, 665),
    ("cabin_25", 596, 642), ("cabin_26", 612, 685),
    ("cabin_27", 627, 715), ("cabin_28", 599, 737),
    ("cabin_29", 570, 752), ("cabin_30", 542, 771),
    ("cabin_31", 514, 790),
)


def regions():
    return list(CLASSIC_HOTSPOTS) + [(name, (x - 13, y - 16, 26, 32)) for name, x, y in CLASSIC_CABINS]


def center(rect):
    x, y, width, height = rect
    return x + width // 2, y + height // 2
