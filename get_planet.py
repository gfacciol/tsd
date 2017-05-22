#!/usr/bin/env python
# vim: set fileencoding=utf-8
# pylint: disable=C0103

"""
Automatic download and crop Planet images.

Copyright (C) 2016-17, Carlo de Franchis <carlo.de-franchis@m4x.org>
"""

from __future__ import print_function
import os
import sys
import time
import shutil
import argparse
import multiprocessing
import numpy as np
import utm
import dateutil.parser

import planet

import utils
import parallel
import search_planet
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from stable.scripts.midway import midway_on_files
from stable.scripts import registration

client = search_planet.client
    

def fname_from_metadata(d):
    """
    Build a string using the image acquisition date and identifier.
    """
    scene_id = d['id']
    date_str = d['properties']['acquired']
    date = dateutil.parser.parse(date_str).date()
    return '{}_scene_{}'.format(date.isoformat(), scene_id)


def metadata_from_metadata_dict(d):
    """
    Return a dict containing some string-formatted metadata.
    """
    imaging_date = dateutil.parser.parse(d['properties']['acquired'])
    sun_zenith = 90 - d['properties']['sun_elevation']  # zenith and elevation are complementary
    sun_azimuth = d['properties']['sun_azimuth']

    return {
        "IMAGING_DATE": imaging_date.strftime('%Y-%m-%dT%H:%M:%S'),
        "SUN_ZENITH": str(sun_zenith),
        "SUN_AZIMUTH": str(sun_azimuth)
    }


def get_download_url(item, asset_type):
    """
    """
    assets = client.get_assets(item).get()

    if asset_type not in assets:
        return

    asset = assets[asset_type]
    if asset['status'] == 'inactive':
        activation = client.activate(asset)
        r = activation.response.status_code
        if r != 202:
            print('activation of item {} asset {} returned {}'.format(item['id'],
                                                                      asset_type,
                                                                      r))
        else:
            return get_download_url(item, asset_type)

    elif asset['status'] == 'activating':
        time.sleep(3)
        return get_download_url(item, asset_type)

    elif asset['status'] == 'active':
        return asset['location']


def download_crop(outfile, item, asset, ulx, uly, lrx, lry, utm_zone=None):
    """
    """
    url = get_download_url(item, asset)
    if url is not None:
        utils.crop_with_gdal_translate(outfile, '/vsicurl/{}'.format(url), ulx,
                                       uly, lrx, lry, utm_zone)


def get_time_series(aoi, start_date=None, end_date=None,
                    item_types=['PSScene3Band'], asset_type='analytic',
                    out_dir='',
                    parallel_downloads=multiprocessing.cpu_count()):
    """
    Main function: download and crop of Planet images.
    """
    # list available images
    images = search_planet.search(aoi, start_date, end_date,
                                  item_types=item_types)['features']
    # Choose from:
    #   all
    #   PSScene4Band
    #   PSScene3Band
    #   REScene
    #   REOrthoTile
    #   Sentinel2L1C
    #   PSOrthoTile
    #   Landsat8L1G

    print('Found {} images'.format(len(images)))

    # build filenames
    fnames = [os.path.join(out_dir, '{}.tif'.format(fname_from_metadata(x)))
              for x in images]

    # convert aoi coordinates to utm
    ulx, uly, lrx, lry, utm_zone = utils.utm_bbx(aoi)

    # activate images and download crops
    utils.mkdir_p(out_dir)
    print('Downloading {} crops...'.format(len(images)), end=' ')
    parallel.run_calls(download_crop, list(zip(fnames, images)),
                       parallel_downloads, 120, asset_type,
                       ulx, uly, lrx, lry, utm_zone)

    # embed some metadata in the image files
    for f, img in zip(fnames, images):  # embed some metadata as gdal geotiff tags
        if os.path.isfile(f):
            for k, v in metadata_from_metadata_dict(img).items():
                utils.set_geotif_metadata_item(f, k, v)

    return

    # register the images through time
    if register:
        if debug:  # keep a copy of the cropped images before registration
            bak = os.path.join(out_dir, 'no_registration')
            utils.mkdir_p(bak)
            for bands_fnames in crops:
                for f in bands_fnames:  # crop to remove the margin
                    o = os.path.join(bak, os.path.basename(f))
                    utils.crop_georeferenced_image(o, f, lon, lat, w-100, h-100)

        registration.main(crops, crops, all_pairwise=True)

        for bands_fnames in crops:
            for f in bands_fnames:  # crop to remove the margin
                utils.crop_georeferenced_image(f, f, lon, lat, w-100, h-100)

    # equalize histograms through time, band per band
    if equalize:
        if debug:  # keep a copy of the images before equalization
            bak = os.path.join(out_dir, 'no_midway')
            utils.mkdir_p(bak)
            for bands_fnames in crops:
                for f in bands_fnames:
                    shutil.copy(f, bak)

        for i in xrange(len(bands)):
            midway_on_files([crop[i] for crop in crops if len(crop) > i], out_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=('Automatic download and crop '
                                                  'of Planet images'))
    parser.add_argument('--geom', type=utils.valid_geojson,
                        help=('path to geojson file'))
    parser.add_argument('--lat', type=utils.valid_lat,
                        help=('latitude of the center of the rectangle AOI'))
    parser.add_argument('--lon', type=utils.valid_lon,
                        help=('longitude of the center of the rectangle AOI'))
    parser.add_argument('-w', '--width', type=int, help='width of the AOI (m)')
    parser.add_argument('-l', '--height', type=int, help='height of the AOI (m)')
    parser.add_argument('-s', '--start-date', type=utils.valid_date,
                        help='start date, YYYY-MM-DD')
    parser.add_argument('-e', '--end-date', type=utils.valid_date,
                        help='end date, YYYY-MM-DD')
    parser.add_argument('--item-types', nargs='*', default=['PSScene3Band'],
                        help=('choose from PSScene4Band, PSScene3Band, REScene,'
                              'REOrthoTile, Sentinel2L1C, PSOrthoTile,'
                              'Landsat8L1G'))
    parser.add_argument('--asset', default='analytic',
                        help=('choose from analytic, visual, basic'))
    parser.add_argument('-r', '--register', action='store_true',
                        help='register images through time')
    parser.add_argument('-m', '--midway', action='store_true',
                        help='equalize colors with midway')
    parser.add_argument('-o', '--outdir', type=str, help=('path to save the '
                                                          'images'), default='')
    parser.add_argument('-d', '--debug', action='store_true', help=('save '
                                                                    'intermediate '
                                                                    'images'))
    parser.add_argument('--parallel-downloads', type=int, default=10,
                        help='max number of parallel crops downloads')
    args = parser.parse_args()

    if args.geom and (args.lat or args.lon or args.width or args.height):
        parser.error('--geom and {--lat, --lon, -w, -l} are mutually exclusive')

    if not args.geom and (not args.lat or not args.lon):
        parser.error('either --geom or {--lat, --lon} must be defined')

    if args.geom:
        aoi = args.geom
    else:
        aoi = utils.geojson_geometry_object(args.lat, args.lon, args.width,
                                            args.height)
    get_time_series(aoi, start_date=args.start_date, end_date=args.end_date,
                    item_types=args.item_types, asset_type=args.asset,
                    out_dir=args.outdir, parallel_downloads=args.parallel_downloads)