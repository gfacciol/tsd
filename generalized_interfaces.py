#!/usr/bin/env python
# vim: set fileencoding=utf-8
# pylint: disable=C0103

"""
Wrapper for Sentinel-2 and Landsat-8 image download from AWS.

Copyright (C) 2017-18, Gabriele Facciolo <facciolo@cmla.ens-cachan.fr>

"""
from __future__ import print_function

import tsd


def search_aoi(aoi, start_date=None, end_date=None, satellite='Landsat-8'):
    '''
    query devseed database for images covering an area of interest (aoi)
    returns a dictionary containing the metadata of all images: res['results']
    '''
    return tsd.search_devseed.search(aoi, satellite=my_satellite) 


def identify_satellite_from_metadata(q):
    '''
    identify the satellite given a the metadata result from search
    '''
    # take the first enrty of the full medatada list
    if type(q) in [list,tuple]:
        q=q[0]
    # this is hakcy to identify a satellite from its medatada
    if 'spacecraft_name' in q:
        return 'Sentinel-2'
    elif 'sensor' in q and q['sensor'] == 'OLI_TIRS':
        return 'Landsat-8'
    else:
        return 'unknown'

    
def aws_get_crop_from_aoi(basename, aoi, image_metadata, bands):
    '''
    This function 
    * Determines the satellite associated to the current image_metadata
    * Computes the url of the image for the selected bands
    * Downloads a crop corresponding to the selected aoi (area of interest)
    * Writes the output as:   [ basename + BAND + '.tif' ]
    Bands are of the form 'B03' for landsat
                        and '8' for sentinel
    '''
    
    if type(bands) not in [list,tuple]:
        bands=[bands]

    satellite = identify_satellite_from_metadata(image_metadata)
    
    #  determine the URL of the ENTIRE image then crop
    files = []
    for bn in bands:
        if satellite=='Sentinel-2':
            srcurl = tsd.get_sentinel2.aws_url_from_metadata_dict(image_metadata, band=bn) 
        elif satellite=='Landsat-8':
            srcurl = tsd.get_landsat.aws_url_from_metadata_dict(image_metadata, band=bn) 
        print('URL of the file we are cropping: '+str(srcurl))

        # convert aoi coordinates to utm
        ulx, uly, lrx, lry, utm_zone, latband = tsd.utils.utm_bbx(aoi)

        # get the cropped image
        tsd.utils.crop_with_gdal_translate(basename+bn+'.tif', srcurl, ulx, uly, lrx, lry, utm_zone, latband)
        files.append(basename+bn+'.tif')
    return files

