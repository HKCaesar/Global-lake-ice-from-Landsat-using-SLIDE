# // This script calculate lake ice percentage from landsat imageries
# // by: Xiao Yang
# // 11/04/2018

import ee
import argparse
import math
from functions import *

parser = argparse.ArgumentParser(prog = 'Download_landsat_lake_ice_data.py', description = "")

parser.add_argument('-sy', '--start_year', help = 'starting (inclusive) year of the export data', type = int, default = 2001)
parser.add_argument('-sm', '--start_month', help = 'starting (inclusive) month of the export data', type = int, default = 8)
parser.add_argument('-ey', '--end_year', help = 'end (inclusive) year of the export data', type = int, default = 2001)
parser.add_argument('-em', '--end_month', help = 'end (inclusive) month of the export data', type = int, default = 9)

parser.add_argument('-minc', '--minimal_cloud_score', help = 'minimal (inclusive) cloud score to include', type = int, default = 0)
parser.add_argument('-maxc', '--maximum_cloud_score', help = 'maximum (inclusive) cloud score to include', type = int, default = 25)

parser.add_argument('-o', '--output_dir', help = 'output directory in the Google drive', type = str, default = 'default')

parser.add_argument('--restart_no', help = 'index to start the task from', type = int, default = 0)

args = parser.parse_args()
start_year = args.start_year
start_month = args.start_month
end_year = args.end_year
end_month = args.end_month
minc = args.minimal_cloud_score
maxc = args.maximum_cloud_score
output_dir = args.output_dir
rs = args.restart_no

ee.Initialize()

def copyPropertiesGen(i):
    def copyLSProperties(f):
        return(f.copyProperties(i, ['LANDSAT_SCENE_ID', 'CLOUD_COVER_LAND'], None))
    return(copyLSProperties)


def calc_lake_ice_image(i):
    hlFil = (ee.FeatureCollection("users/eeProject/HydroLAKES_polys_v10")
    .filterMetadata('Lake_area', 'not_greater_than', 1)
    .filterMetadata('Lake_area', 'greater_than', 0.045))

    fmask = addFmask(i).select('fmask')
    i = i.addBands(fmask.eq(3).rename(['snowIce']))
    i = i.addBands(fmask.eq(2).Or(fmask.eq(4)).rename(['cloud']))
    i = i.addBands(fmask.eq(1).rename(['water']))
    i = i.addBands(fmask.eq(0).rename(['clear']))
    i = (i
    .select(['snowIce', 'cloud', 'water', 'clear'])
    .mask(wocc.gte(90))
    .updateMask(fmask.gte(0)))

    copyLSProperties = copyPropertiesGen(i)
    lakesFil = hlFil.filterBounds(i.geometry()).map(copyLSProperties)

    pc = (i.reduceRegions(
    collection = lakesFil,
    reducer = ee.Reducer.mean(),
    scale = 30,
    crs = None,
    tileScale = 1))

    return(pc)

ls = (merge_collections_std_bandnames_collection1tier1()
.filterMetadata('CLOUD_COVER_LAND', 'not_less_than', minc)
.filterMetadata('CLOUD_COVER_LAND', 'not_greater_than', maxc))
hl = ee.FeatureCollection("users/eeProject/HydroLAKES_polys_v10")

jrc = ee.Image("JRC/GSW1_0/GlobalSurfaceWater")

n = (end_year - start_year) * 12 + (end_month - start_month) + start_month + 1

if output_dir == 'default':
    output_dir = 'lake_ice_landsat578_collection1_tier1_' + 'cs' + str(minc) + '-' + str(maxc) + '_' + str(start_year) + '-' + str(start_month) + '_' + str(end_year) + '-' + str(end_month)

for i in range(start_month + rs, n):

    yearOffset = math.floor((i - 1) / 12)
    year = int(start_year + yearOffset)
    month = int(i - yearOffset * 12)

    year_offset_next = math.floor(i / 12)
    year_next = int(start_year + year_offset_next)
    month_next = int(i + 1 - year_offset_next * 12)

    t_start = str(year) + '-' + format(month, '02d') + '-01'
    t_end = str(year_next) + '-' + format(month_next, '02d') + '-01'

    wocc = jrc.select(['occurrence'])
    hlFil = hl.filterMetadata('Lake_area', 'greater_than', 1)

    lsFiltered = ls.filterDate(t_start, t_end)

    result = lsFiltered.map(calc_lake_ice_image).flatten()
    fn = 'small_lake_state_cs_' + format(minc, '02d') + '-' + format(maxc, '02d') + '_' + t_start

    task = (ee.batch.Export.table.toDrive(
            collection = result.select(propertySelectors = ['Hylak_id', 'cloud', 'snowIce', 'water', 'LANDSAT_SCENE_ID', 'CLOUD_COVER_LAND'], retainGeometry = False),
            description = fn,
            folder = output_dir,
            fileNamePrefix = fn,
            fileFormat = 'CSV'))

    task.start()

    maximum_no_of_tasks(5, 120)

    print('task', i - start_month + 1, 'of', n - start_month, ', (', t_start, t_end, ')', 'has submitted.')
