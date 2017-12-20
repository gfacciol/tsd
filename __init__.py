import os
import sys
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

import utils
import search_devseed
try:
    import search_scihub
except SystemExit:
    pass
try:
    import search_planet
except SystemExit:
    pass

import get_landsat
import get_sentinel2
try:
    import get_sentinel1
except SystemExit:
    pass
try:
    import get_planet
except SystemExit:
    pass

from generalized_interfaces import aws_get_crop_from_aoi as aws_get_crop_from_aoi
from generalized_interfaces import identify_satellite_from_metadata as identify_satellite_from_metadata